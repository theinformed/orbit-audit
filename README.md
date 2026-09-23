# Registered manoeuvre detection from two-line element sets

This repository is the public release of a research programme on **detecting
orbital manoeuvres from public two-line element (TLE) sets**, and on **bounding
the false alarms that such detection produces**. It contains the papers, the
pre-registrations they were executed under, the machine receipts behind every
number they report, and the analysis and site code that produced them.

The central methodological problem is that manoeuvre detection from public
element sets has no ground truth: operators do not publish burn logs, so a
detector's precision cannot be measured directly. The apparatus here answers
that by using the catalogue's **passive population** — debris and spent rocket
bodies, which are passive by physical class — as a continuously measured
negative control, carrying each population's rate as an interval rather than a
point estimate, and binding the public wording of every individual detection to
a bound-versus-bound separation requirement recomputed on each run. When the
requirement is not met the word "manoeuvre" is withheld and a stated reason is
published in its place.

The detector audits itself in public, and this release includes the occasions on
which it **failed its own gate**. That is deliberate: a false-alarm control that
only ever reports success is not a control.

## Papers

| | | |
|---|---|---|
| **Paper A** | [Does station-keeping relax before retirement? A registered, population-scale observational test in the geostationary belt](docs/paper-a-draft-20260921.md) | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22884814.svg)](https://doi.org/10.5281/zenodo.22884814) |
| **Paper B** | [A continuously audited, publicly gated false-alarm control for manoeuvre detection from two-line element sets](docs/paper-b-draft-20260921.md) | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22884816.svg)](https://doi.org/10.5281/zenodo.22884816) |
| **Paper D** | [A public, audited record of orbit changes: episodes, their reading, and the numbers that license every entry](docs/paper-d-draft-20260923.md) | draft, 2026-09-23 |

All three are by **Sean D. Egan and Derek Conklin**, released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (the repository's own
Apache 2.0 license, below, covers the code; the papers themselves are CC BY).
Papers A and B are dated 2026-09-21 and have DOIs. **Paper D is a draft, dated
2026-09-23, and has no DOI**: it has not been deposited, and `CITATION.cff`
will not name it until it has. LaTeX sources and built PDFs are under
[`docs/latex/`](docs/latex/) — [paper A](docs/latex/paper-a/paper-a.pdf)
(22 pages), [paper B](docs/latex/paper-b/paper-b.pdf) (28 pages) and
[paper D](docs/latex/paper-d/paper-d.pdf) (33 pages).

Every numeric claim in each draft is followed by an HTML comment of the form
`<!-- src: ... -->` naming the document or machine receipt it was taken from.
Nothing was recomputed or estimated while drafting. Comments marked
`derivation:` instead of `src:` are arithmetic performed for the draft from
numbers that are themselves traced, and are marked so that no reader mistakes a
derivation for a receipt. Every document named in those comments is in this
repository, under `docs/`, with the single exception named in
[`DATA.md`](DATA.md).

`docs/latex/check-numbers.py` is the acceptance test for the typesetting: it
extracts every numeric token from a draft and from the `.tex` built from it and
diffs the two ordered sequences, so a single altered digit fails.

```bash
cd docs/latex
python3 check-numbers.py ../paper-a-draft-20260921.md paper-a/paper-a.tex
python3 check-numbers.py ../paper-b-draft-20260921.md paper-b/paper-b.tex
python3 check-numbers.py ../paper-d-draft-20260923.md paper-d/paper-d.tex
```

Paper A reports two results in order: cessation of north-south station-keeping
is **not** a retirement proxy, and the registered test of the folklore that
motivates it came out **underpowered** rather than positive or null. Paper B
reports the false-alarm apparatus, one worked detector change carried end to end
under pre-registration, and — at equal prominence — two registered stress tests
the apparatus failed, including a full-archive re-measurement that shut the gate
at 5.3560x against an unchanged 10x separation requirement.

Paper D describes the published record of orbit changes itself: 1,992 episodes
assembled from 2,058 detected steps, a forward horizon that stops at +20 days
because that is where the measured error stops resolving one occupied longitude
from the next, a type library that leaves 80.0% of near-geostationary burns
unlabelled, a detection recall of 7.94% against the best-labelled population
available, and an alarm whose low-orbit arm publishes a withheld gate instead
of an alert. Its registrations, results documents and receipts are in `docs/`,
and its figures are rebuilt with `python3 tools/make_figures.py paper-d`.
Appendix A of the draft identifies each measurement's registration and result
by the commit that first carries the document, in the working repository this
release was cut from rather than in this one; the documents those commits
carry are all in `docs/`.

## Reproducibility and registration

Analyses here were **pre-registered before they were run**. The pre-registration
documents are in `docs/*preregistration*.md`, and each states its hypotheses,
its decision rules and its stopping conditions ahead of the measurement, so a
result that failed its own registered gate could not be quietly re-scoped
afterwards. Several were.

The registrations are anchored in time using
[OpenTimestamps](https://opentimestamps.org), which commits a hash to the
Bitcoin blockchain and therefore proves a document existed no later than a given
block — independently of this repository, its history, or its authors.

There are two anchored manifests, and between them they cover every registration
document in this release:

| Manifest | Proof | Covers |
|---|---|---|
| [`registration-anchor-manifest-20260921.txt`](docs/registration-anchor-manifest-20260921.txt) | [`.ots`](docs/registration-anchor-manifest-20260921.txt.ots) | the phase-3, repricing, cadence and Paper B pre-registrations |
| [`registration-anchor-manifest2-20260921.txt`](docs/registration-anchor-manifest2-20260921.txt) | [`.ots`](docs/registration-anchor-manifest2-20260921.txt.ots) | the correction-quantum and route2-weighing registration sets (13 documents) |

Each manifest lists the SHA-256 of every document it covers. To verify, upload a
manifest and its `.ots` proof to the verifier at <https://opentimestamps.org>,
or use the command-line client:

```bash
pip install opentimestamps-client
ots verify docs/registration-anchor-manifest-20260921.txt.ots
ots verify docs/registration-anchor-manifest2-20260921.txt.ots
```

Then confirm the documents still hash to what the manifests recorded:

```bash
sha256sum -c <(grep -E '^[0-9a-f]{64}  docs/' docs/registration-anchor-manifest-20260921.txt)
sha256sum -c <(grep -E '^[0-9a-f]{64}  docs/' docs/registration-anchor-manifest2-20260921.txt)
```

## Repository layout

```
docs/          the papers, the pre-registrations, and every results,
               receipt, strata and lines artifact the papers cite
docs/latex/    LaTeX sources, the Markdown-to-LaTeX converter, the number checker
               and the built PDFs
pipeline/      the detection and release pipeline: TLE archive, campaign and
               interval construction, the event detector, drift analysis
               (CPU and GPU), columnar storage, and release assembly
tools/         the analysis programs behind the papers - cadence, repricing,
               phase 3, strata, fuel odometer, end-of-life studies - plus
               benchmarks, verification harnesses and this release's gate
tests/         the test suite, including the orbit detector suite
src/           the browser application that publishes the detector's output
ingest/        upstream mirrors (Space-Track, CelesTrak, GCAT, SuperMAG)
ops/           scheduling, cadence and bandwidth accounting for the published site
narration/     narration scripts and fact packets for the application's audio
public/        static assets served alongside the built application
deploy/        the publication path: container, nginx and systemd definitions
data/          reference and override data the pipeline reads
```

[`DATA.md`](DATA.md) sets out every upstream product the analyses read, its
distributor and its licence, and what is published here in place of it.

## Hosts and configuration

No credentials, keys or tokens appear anywhere in this repository, and no
private network address does either. Everything host-specific is read from the
environment, with a placeholder default so that an unconfigured checkout cannot
silently talk to somebody else's machine:

| Variable | Used by | Placeholder default |
|---|---|---|
| `ORBIT_PUBLISH_SSH_HOST` | `pipeline/publish_vps.sh` | `root@publisher.example.invalid` |
| `ORBIT_ARCHIVE_BIND` | `deploy/orbit-archive.compose.yaml` | `127.0.0.1` |
| `SPACE_MODEL_URL` | `pipeline/catalog_factcheck.py` | `http://model-host.example.invalid:18080/v1/chat/completions` |
| `SPACE_MODEL_NAME` | `pipeline/catalog_factcheck.py` | `bigmem-chat` |
| `ORBIT_ARCHIVE_DB` | the analysis instruments in `tools/` | `element-archive.not-configured.sqlite3` |
| `ORBIT_TRUTHSET_ROOT` | `tools/truthset_*.py`, `tools/differential_detect.py` | `truthset.not-configured` |
| `ORBIT_COLUMN_CACHE` | `tools/per_object_noise.py` | `element-column-cache.not-configured` |
| `ORBIT_TRIGGER_WORK` | `tools/kinematic_inputs.py` | `trigger-alarm-work.not-configured` |
| `ORBIT_PLANE_WORK` | `tools/kinematic_inputs.py` | `plane-detect-work.not-configured` |
| `ORBIT_NODE` | `tools/truthset_growth.py` | whatever `node` is on `PATH` |
| `SUPGP_FETCH_HOST` | `tools/supgp_ingest.py` | `supgp-lane.example.invalid` |
| `EPHEMERIS_FETCH_HOST` | `tools/supgp_ingest.py`, `tools/starlink_collect.py` | `ephemeris-lane.example.invalid` |
| `SUPPLEMENTAL_ARCHIVE_ROOT` | `tools/supgp_ingest.py`, `tools/starlink_collect.py` | `supplemental-archive.not-configured` |

`ORBIT_ARCHIVE_BIND` is a security boundary rather than a convenience: the
archive container must publish on exactly one address, and the loopback default
is the safe one. Do not set it to `0.0.0.0`.

The two `*_FETCH_HOST` variables are boundaries too. Each upstream provider
counts requests per account and per address, so each fetching lane is pinned to
one machine; the placeholder matches no real host, and an unconfigured checkout
refuses to open the socket rather than fetching from wherever it is run.

Everything else above is a filesystem location that is a property of an
installation rather than of the code. Working directories are not in this table
because they are not defaulted at all: they are required command-line
arguments. The offline test suites need none of this.

## Building and testing

### Python analysis and pipeline

Python 3.12 with NumPy. The orbit detector suite is the acceptance test for the
analysis code:

```bash
python3 -m unittest discover -s tests -p 'test_orbit*.py'
```

This runs 820 tests and must report `OK (skipped=5)`. The skips are GPU paths
that need CUDA hardware.

It does not cover everything. The approach, alarm, type-library, truth-set and
control instruments behind paper D carry suites of their own, and the wider run
is what covers them:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

That runs 3057 tests and must report `OK (skipped=121)`. Every test in
either run builds its own fixture: no archive, no network and no credentials,
so a fresh clone runs the whole suite as it stands.

Optional environments, both isolated from the system interpreter:

```bash
pip install -r requirements-orbit-drift-gpu.txt   # CuPy GPU drift path
pip install -r tools/eol-analysis-requirements.txt  # offline end-of-life analysis
```

### Browser application

The TypeScript application that publishes the detector's output is included for
review and reuse. Node with npm:

```bash
npm install
npm run check      # TypeScript project check
npm test           # vitest unit tests
npm run build      # production build
npm run dev        # local development server
```

Some suites under `tests/` are Playwright browser specs (`*.spec.ts`) and need
`npx playwright install` before `npm run test:browser`. The application reads
published data artifacts at runtime; those artifacts are produced by the
pipeline and are not checked in, so a local build renders the interface without
live data.

### Rebuilding the papers

```bash
cd docs/latex/paper-a && pdflatex -halt-on-error paper-a.tex && pdflatex -halt-on-error paper-a.tex
cd ../paper-b        && pdflatex -halt-on-error paper-b.tex && pdflatex -halt-on-error paper-b.tex
```

Two passes are needed for cross-references. The committed `.tex` files are the
source of record; `md2tex.py` is kept so the original conversion is reproducible
and is not to be re-run over hand edits.

### Release gate

```bash
tools/release_gate.sh
```

The gate is a mechanical check that this repository names no AI vendor or coding
assistant in any file, content or filename, with one deliberate exception: the
Acknowledgments sentence carried by the papers, which is a required
disclosure and is whitelisted verbatim and counted exactly. The script documents
how it reads text, PDF and binary files, and exits non-zero on any violation.

## Data sources

Orbital elements come from Space-Track OMM/SATCAT and CelesTrak mirrors under
their respective terms of use. This repository contains analysis code, reference
data and results documents; it does not redistribute the element archive itself,
which is 216.9 million rows at the time of papers A and B and 217.0 million at
the time of paper D.

[`DATA.md`](DATA.md) is the full account: every upstream product the analyses
read, its distributor, its licence and its identifier; what is published here
instead of each one; the one receipt that is withheld and why; and the
environment variables that point the tools at a local copy of the raw
material.

## License

Copyright the authors. Licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE). You may obtain a copy of the license at
<https://www.apache.org/licenses/LICENSE-2.0>.
