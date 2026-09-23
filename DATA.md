# Data: what is published here, what is not, and under what terms

This repository publishes **analysis code, pre-registrations, results
documents, machine receipts and figure sources**. It does **not** republish the
bulk upstream products those analyses ran over. This file says which is which,
names the licence and the identifier of every upstream product, and says where
each one comes from, so a reader can obtain the raw material and re-run the
measurement.

The rule is one line: **raw data stays with its distributor; the derived
receipts are published here.**

## What is published

| Kind | Where | What it is |
|---|---|---|
| Pre-registrations | `docs/*preregistration*.md`, `docs/*registration*.md` | each measurement's estimand, thresholds, gates and decision rules, committed before the instrument existed |
| Results documents | `docs/*-results-*.md` | what each measurement returned, including the registered bars it missed |
| Machine receipts | `docs/*-receipt.json`, `docs/*.json`, `docs/*.jsonl` | the per-run provenance, and the per-object or per-event rows a results document summarises |
| Figure sources | those same receipts, read by `tools/make_figures.py` | every figure in every paper is drawn from a committed artifact, never from a live archive read |
| Analysis code | `pipeline/`, `tools/`, `ingest/`, `ops/` | the instruments themselves, with their offline test suites under `tests/` |

Every numeric claim in a paper draft carries an HTML comment naming the
document or receipt it was taken from, and every document so named is in this
repository with one exception: paper D's section 7 cites the programme's own
operational runbook for its deployment and attestation record. That runbook is
a working document of the machines this research runs on rather than a research
artifact, it names the tooling the release gate forbids, and it is not
published. Everything it is cited for — which registrations are anchored, and
that the release passed its gates — is either checkable from the anchored
manifests in `docs/` or is a fact about a deployment rather than about a
measurement.

## What is not published, and why

None of the following is redistributed here. Each is a bulk product held by a
distributor who publishes it under its own terms; re-hosting a copy would add
nothing a reader cannot fetch, and in two cases the terms do not permit it.

| Product | Source | Terms | Used by |
|---|---|---|---|
| **Element-set archive** — 217,046,214 rows over 68,749 objects, about 13.9 GB of SQLite | Space-Track OMM/SATCAT and the CelesTrak mirrors | Space-Track user agreement: per-account, not redistributable | nearly every instrument here |
| **Supplemental ephemerides** — large-constellation operator ephemerides, 72-hour spans tabulated at 60 s, and the supplemental general-perturbations sets | the operator's own public ephemeris files, and CelesTrak's supplemental GP service | each distributor's terms of use; fetched one lane at a time from one pinned host, and not redistributed | `tools/covariance_realism.py`, `tools/starlink_collect.py`, `tools/supgp_ingest.py` |
| **Precise orbit ephemerides, Sentinel-1A** — `AUX_POEORB`, Earth-Explorer XML, 10 s | Registry of Open Data on AWS, bucket `s1-orbits`, anonymous | open, no account needed | `tools/truthset_fetch.py`, `tools/truthset_growth.py` |
| **Precise orbit ephemerides, Sentinel-3A / 3B** — CNES/SSALTO POE, SP3-c, version 30 (POE-G) | International DORIS Service data centre, `ftp://doris.ign.fr/pub/doris/products/orbits/ssa/`, anonymous | open | as above |
| **Earth orientation parameters** — IERS `finals2000A.all` | `datacenter.iers.org`, anonymous | open | the TEME-to-ITRF chain in `tools/truthset_truth.py` |
| **Mission-reported manoeuvre histories** — `s3aman.txt`, `s3bman.txt` | `ids-doris.org/documents/BC/satellites/` | open | truth-set corroboration |
| **MAD-LEO annotation tables** — 1,134 mission-evidenced manoeuvres over eleven geodetic and altimetry spacecraft, 5 CSV tables, 1.4 MB | figshare, doi [10.6084/m9.figshare.33446503.v1](https://doi.org/10.6084/m9.figshare.33446503.v1) | **CC BY 4.0** | the recall measurement in `tools/truthset_recall.py` and `tools/per_object_noise.py` |

### On MAD-LEO specifically

Its CC BY 4.0 licence *would* permit redistribution with attribution. It is
nevertheless not mirrored here, and the choice is deliberate: a label set is
most useful from its own canonical DOI, where its version, its errata and its
citation record live, and a second copy elsewhere is a way for the two to drift
apart. What this repository publishes instead is the **derived receipts** —
which labels the detector matched, which it missed, and at what burn size — in
`docs/t16b-truthset-recall-20260922.json`,
`docs/t16b-truthset-growth-20260922.json` and
`docs/t27-per-object-noise-20260923.json`.

Attribution, as the licence requires: Guo, Z., Shi, Q., Xu, X., Ge, L., Zhu, H.,
Ben, L., Nie, B., Zhao, Y., & Li, X. (2026). *MAD-LEO: a maneuver-annotated
orbital dataset for LEO satellites with tiered multi-source evidence.* arXiv
preprint arXiv:2609.08556. Dataset: figshare,
doi 10.6084/m9.figshare.33446503.v1, CC BY 4.0.

## One withheld receipt, named

`docs/t18-capitulation-ledger-20260922.jsonl` — the single-row adversarial-pass
ledger the T18 registration requires — is **not** in this repository, although
`docs/t18-fail-record-20260922.md` and `docs/t18-floor-results-20260922.md`
refer to it by path. Its registered `whoRan` field names the tool that ran the
pass, which the release gate (`tools/release_gate.sh`) forbids any file here to
name, and rewriting a field of a registered record to get past a gate would be
worse than omitting the record. What the ledger holds — one pass, verdict
`revised`, and exactly what it changed — is stated in full in section 10 of the
fail record, which is published.

## Where a released file is not the file a receipt pinned

Each measurement's receipt records the SHA-256 of the code that produced it.
A few files here do not hash to what an older receipt recorded, for two reasons
and only two: the released copy differs from the measured copy in comments,
docstrings and installation-specific path defaults; or the instrument was
revised later in the programme, after that receipt was written.
`docs/released-source-hashes-20260923.json` names every such file, the hashes
it supersedes, which reason applies and where each superseded hash was
recorded. No receipt was edited to match a later file.
`tests/test_released_sources.py` sweeps every receipt and fails on any recorded
hash that neither matches its file nor is accounted for there.

## Pointing the tools at a local copy

Nothing here has a path default that resolves on one particular machine. Each
installation-specific location is named by an environment variable and falls
back to a placeholder that cannot resolve, so an unconfigured checkout fails
with the name of the variable it needs rather than reading whatever happens to
sit at somebody else's path. Working directories are ordinary command-line
arguments, and they are required rather than defaulted.

| Variable | Points at |
|---|---|
| `ORBIT_ARCHIVE_DB` | the element-set archive database |
| `ORBIT_TRUTHSET_ROOT` | the directory `tools/truthset_fetch.py` writes precise-orbit products and label tables into |
| `ORBIT_COLUMN_CACHE` | the element-set column cache the type library and the per-object arm read |
| `ORBIT_TRIGGER_WORK` | the trigger-time predictor's working directory |
| `ORBIT_PLANE_WORK` | the plane detector's frozen extract directory |
| `ORBIT_NODE` | a `node` binary, when one is not on `PATH` (the SGP4 bridge) |
| `SUPPLEMENTAL_ARCHIVE_ROOT` | the directory the supplemental-ephemeris lanes fetch into |
| `SUPGP_FETCH_HOST`, `EPHEMERIS_FETCH_HOST` | the one machine each fetching lane may run on |

The offline test suites need none of these. Every test builds its own fixture
and asserts an arithmetic fact about it, so a fresh clone runs the whole suite
with no archive, no network and no credentials.
