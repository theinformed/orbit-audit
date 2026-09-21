# bigmem-PC data pipeline

All upstream ingestion and scientific processing for Space Environment Explorer runs here on
`bigmem-PC`. The public VPS serves the resulting files and never performs catalog joins, NetCDF
work, model execution, or language-model enrichment.

`build_release.py` reads hourly Space-Track OMM/SATCAT mirrors for orbital data. A separate
VPS-only CelesTrak mirror contributes operational/category metadata under a six-hour outbound
gate, without a duplicate bulk-elements download. The pipeline also reduces NOAA SWPC
observations, GloTEC, OVATION, operational BATS-R-US cut planes, and
coupled RBE electron fields, joins and classifies the satellite catalog, then publishes
content-addressed artifacts behind one atomically replaced `manifest.json`.

Every release also fetches the current native NOAA D-RAP and OVATION numeric grids and snapshots
them under `/mnt/d/space-explorer/environment-history` on bigmem. The browser artifacts contain
only the requested rolling 48-hour window. They report the exact available range, frame count,
coverage duration, and every cache gap; the reducer never holds a stale frame beyond its published
validity allowance, interpolates between times, reconstructs OVATION probabilities from NOAA's
rendered image loop, or invents a missing hemisphere. A cold OVATION cache is necessarily partial
because NOAA publicly distributes only its latest numeric grid. D-RAP's separate NCEI native archive
can be reduced for curated history, but the ordinary release job deliberately avoids a roughly
60 MB-per-day archive backfill. If either live parser or fetch fails, the manifest keeps that
product's last-known-good content-addressed artifact when its file is still present.

The geospace family (radiation belts and the retained SWMF cuts) is archived the same way, under
`/mnt/d/space-explorer/environment-history/geospace`, by `geospace_history.py`. It differs from its
two siblings in three respects, all forced by frame size. The archive stores the complete reduced
frame but the *published* archive carries only `radiationBelt`, `structures`, and an empty `planes`
object, because the cut-plane fields are roughly 70% of a frame and feed only the hidden
`layer-geospace` control. The published archive is thinned onto a fixed UTC grid — the finest
cadence on `CADENCE_LADDER_MINUTES` that keeps it inside `MAX_PUBLISHED_ARCHIVE_FRAMES` — and that
cadence is uniform on purpose, because the browser will not bridge a gap wider than 2.5x the median
frame spacing. Snapshots are pruned at `SNAPSHOT_RETENTION_HOURS`, roughly 280 MB.

Two offline subcommands exist, neither of which touches a network:
`python3 -m pipeline.geospace_history status` reports what the archive covers, and
`... backfill` reduces NOAA source files already sitting in the disposable
`/mnt/d/space-explorer/swmf-cache` download cache into archive snapshots.

The manifest exposes these rolling products as `drap` and `aurora`. Each record includes
`path`, `sha256`, `frameCount`, `validFrom`, `validTo`, requested bounds, actual coverage hours,
gap count, and a source-retention flag. The full artifacts retain the individual gap intervals and
reasons used by the timeline.

The same release normalizes NOAA's R/S/G scale JSON, recent-message JSON, plain-language 3-Day
Forecast, detailed 3-Day Geomagnetic Forecast, and planetary Kp forecast into `swpc-outlook.v1`.
The deterministic parser preserves nulls and the observed/estimated/predicted Kp phase, keeps each
product's issue time separate, and labels recent alert-feed messages as not necessarily active.

```bash
python3 -m pipeline.build_release
```

The first release deliberately limits the browser catalog to 8,000 representative active objects
while retaining all high-interest mission classes. Large commercial constellations are sampled
deterministically at release construction. In the browser, PNT and constellation/fleet focus views
show every included member without applying the ordinary featured-density ceiling. Use
`--max-satellites 0` only after the full-catalog mobile benchmark passes.

`swmf.py` discovers common one-minute GM/RBE valid times on NOAA NOMADS, downloads scientific files
to `/mnt/d/space-explorer/swmf-cache`, validates Fortran/ASCII schemas, crops the model domain,
quantizes consistent scalar ranges, and emits a six-frame sequence. The raw cache is bigmem-only.
The VPS receives only the content-addressed reduced artifact. The public browser uses the RBE portion;
the two-plane plasma control is hidden until a separately validated full-volume/data-conditioned
phase can present a scientifically meaningful 3-D field.

`wam_ipe.py` discovers all retained NOAA WFS cycles plus the bigmem rolling cache and publishes a
four-hour-cadence 3-D ionosphere sequence covering a requested 48-hour history through the latest
cycle's complete official forecast endpoint. Each 22 MB `ipe10` NetCDF frame is reduced from
90×91×58 to 45×46×30 source points. The retained altitude coordinates run from the published 90 km
floor to 2,655 km. Electron density is the quasi-neutral sum of the seven positive-ion density
fields; their normalized composition is stored in four packed bytes per point. Missing source
values remain an independent bit mask. A cold NOAA listing can expose slightly less than 48 hours,
so the artifact reports requested and actual coverage rather than inventing frames; the 96-hour
local cache supplies the full rolling boundary after scheduled operation. Reduction requires the
system `python3-netcdf4` and `python3-numpy` packages.

The same artifact publishes E/F1 peak surfaces derived from the actual ipe10 vertical profiles and
a five-minute ipe05 HmF2/NmF2 F2 surface. The public renderer displays these triangulated surfaces,
not the old 3-D point cloud. The retained volume remains available for selected-spacecraft sampling.

The SWMF reducer also retains explicit missing/low-clipped/high-clipped masks for every scalar sample.
The browser's default Smooth view performs gap-aware, locally bounded interpolation for readable
contours; Native grid remains available for the unresampled adaptive samples. Interpolation never
crosses a missing nearest sample and is clamped to its contributing source values, so it cannot
invent a new scalar extremum.

These retained cut-plane products are phase-2 constraints rather than a public pseudo-volume.
Dayside structures are derived conservatively from the actual y=0 and z=0 model cuts. Density,
thermal-pressure, and velocity transitions provide raywise bow-shock proxies; a current-density
ridge supported by an inward density drop provides a magnetopause proxy. Compact in-plane magnetic
and bulk-flow streamlines are traced only where the corresponding projected vector is meaningful.
Every flow point retains the BATS-R-US velocity magnitude, allowing frozen-frame tracers to slow
and deflect with the modeled plasma rather than follow a straight empirical path. Lines terminate
at the model crop or inner boundary and browser advection rejects any segment that crosses Earth.
A browser loft may use both orthogonal profiles as a 3-D cue, but it is not a recovered volumetric
surface. Unsupported angular sectors remain open. The two cuts cannot establish full 3-D magnetic
connectivity, classify cusps, or supply a species-resolved ring current.

The coupled RBE file is a native two-spatial-dimensional equatorial electron solution with 12
energies and 12 equatorial pitch-angle channels. The browser payload retains all 12 pitch channels
for four representative energies. Native equatorial coordinates come from each block's mapped
equatorial radius and MLT columns, not its uniform source-grid MLT; the distinction reaches roughly
0.47 magnetic-local-time hours in the inspected operational frame. Any selected pitch channel remains
available as a separately labeled model-native 2-D view. The optional 3-D view maps every nonempty
published pitch channel as a weighted translucent shell with `r = L cos²(lambda)` and the dipole
mirror condition. It assumes gyrotropy and north/south pitch symmetry and excludes loss-cone channels
that reach the RBE inner boundary. It must be labeled `MULTI-PITCH DIPOLE-MAPPED ELECTRON VOLUME`;
it is not native 3-D RBE output, particle density, a proton/inner-belt model, or a BATS-R-US
field-line trace.

The successful publisher bounds that disposable raw cache to 96 hours with
`prune_swmf_cache.py` (normally about 2 GB at the current 20-minute sampling). Curated historical
event bundles are stored independently and are never inferred from this rolling-cache retention.

The pipeline follows four rules:

1. Preserve upstream timestamps, source identities, quality flags, and nulls.
2. Label every layer observed, assimilated, model, forecast, or schematic.
3. Reject implausibly small catalog/GloTEC responses and keep the prior manifest live.
4. Treat model-written prose as optional cached decoration. Deterministic facts and classifications remain
   independently inspectable, and unknown missions remain unknown.

## Optional local Qwen teaching brief

`enrich_qwen.py` uses two passes against a reasoning-enabled local endpoint, requires non-empty
`reasoning_content`, rejects digits and overlong prose, and keys the candidate to the exact fact
packet. Run only after checking both GPUs and keep it single-flight so it remains a polite guest of
Bob and other local workloads.

```bash
python3 -m pipeline.enrich_qwen --endpoint http://127.0.0.1:PORT/v1/chat/completions
python3 -m pipeline.build_release
```

If the candidate is stale or fails validation, the release automatically keeps its deterministic
fact-bounded brief.
