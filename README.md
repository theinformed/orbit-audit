# Registered manoeuvre detection from two-line element sets

This repository is the public release of a research programme on **detecting
orbital manoeuvres from public two-line element (TLE) sets**, and on **bounding
the false alarms that such detection produces**. It contains the two papers, the
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

Both are drafts by **Sean D. Egan and Derek Conklin**, dated 2026-09-21, released
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (the repository's
own Apache 2.0 license, below, covers the code; the papers themselves are CC BY).
LaTeX sources and built PDFs are under [`docs/latex/`](docs/latex/) —
[paper A](docs/latex/paper-a/paper-a.pdf) (22 pages) and
[paper B](docs/latex/paper-b/paper-b.pdf) (28 pages).

Every numeric claim in both drafts is followed by an HTML comment of the form
`<!-- src: ... -->` naming the document or machine receipt it was taken from.
Nothing was recomputed or estimated while drafting. Comments marked
`derivation:` instead of `src:` are arithmetic performed for the draft from
numbers that are themselves traced, and are marked so that no reader mistakes a
derivation for a receipt. Every document named in those comments is in this
repository, under `docs/`.

`docs/latex/check-numbers.py` is the acceptance test for the typesetting: it
extracts every numeric token from a draft and from the `.tex` built from it and
diffs the two ordered sequences, so a single altered digit fails.

```bash
cd docs/latex
python3 check-numbers.py ../paper-a-draft-20260921.md paper-a/paper-a.tex
python3 check-numbers.py ../paper-b-draft-20260921.md paper-b/paper-b.tex
```

Paper A reports two results in order: cessation of north-south station-keeping
is **not** a retirement proxy, and the registered test of the folklore that
motivates it came out **underpowered** rather than positive or null. Paper B
reports the false-alarm apparatus, one worked detector change carried end to end
under pre-registration, and — at equal prominence — two registered stress tests
the apparatus failed, including a full-archive re-measurement that shut the gate
at 5.3560x against an unchanged 10x separation requirement.

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
docs/          the two papers, the pre-registrations, and every results,
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

`ORBIT_ARCHIVE_BIND` is a security boundary rather than a convenience: the
archive container must publish on exactly one address, and the loopback default
is the safe one. Do not set it to `0.0.0.0`.

## Building and testing

### Python analysis and pipeline

Python 3.12 with NumPy. The orbit detector suite is the acceptance test for the
analysis code:

```bash
python3 -m unittest discover -s tests -p 'test_orbit*.py'
```

This runs 681 tests and must report `OK (skipped=5)`. The skips are GPU paths
that need CUDA hardware. To run the wider Python suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

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
Acknowledgments sentence carried by the two papers, which is a required
disclosure and is whitelisted verbatim and counted exactly. The script documents
how it reads text, PDF and binary files, and exits non-zero on any violation.

## Data sources

Orbital elements come from Space-Track OMM/SATCAT and CelesTrak mirrors under
their respective terms of use. This repository contains analysis code, reference
data and results documents; it does not redistribute the element archive itself,
which is 216.9 million rows at the time of the papers.

## License

Copyright the authors. Licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE). You may obtain a copy of the license at
<https://www.apache.org/licenses/LICENSE-2.0>.
