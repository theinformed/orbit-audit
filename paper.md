---
title: 'orbit-audit: catalogue-scale satellite manoeuvre detection with a continuously measured false-alarm bound'
tags:
  - Python
  - space situational awareness
  - orbital mechanics
  - satellite tracking
  - two-line elements
  - reproducibility
authors:
  - name: Sean D. Egan
    orcid: 0009-0005-9318-8819
    affiliation: 1
  - name: Derek Conklin
    affiliation: 1
affiliations:
  - name: The Informed
    index: 1
date: 22 September 2026
bibliography: paper.bib
---

# Summary

`orbit-audit` detects satellite manoeuvres from publicly available two-line
element (TLE) sets and, unlike prior public detectors, continuously measures
and publicly gates its own false-alarm rate rather than reporting only
detections. Operators do not publish burn logs, so a TLE-based detector's
precision has no ground truth to check it against. `orbit-audit` addresses
this by treating the catalogue's passive population — debris and spent rocket
bodies, which are passive by physical class — as a negative control measured
on every run, expressing its rate as a Jeffreys credible interval rather than
a point estimate, and requiring a pre-registered bound-versus-bound
separation between that control and the payload population before the word
"manoeuvre" is allowed to appear in a published detection. When the
requirement is not met on a given run, the word is withheld and a stated
reason is published instead. The software runs at catalogue scale (216.9
million source element sets across the analyses reported so far), uses
paired GPU/CPU kernels for the drift-detection lane, and regenerates every
published figure deterministically from committed intermediate artifacts.
Pre-registrations of each analysis are timestamp-anchored to the Bitcoin
blockchain via OpenTimestamps before the corresponding measurement is run.
The repository includes cases where the detector's own gate was not met,
because a false-alarm control that only ever reports success is not a
control.

# Statement of need

Manoeuvre detection from TLEs is used by space situational awareness (SSA)
researchers, satellite operators tracking third-party activity, and
reproducibility auditors who need to check a published detection claim
against the data and code that produced it. All three audiences face the
same obstacle: TLE-based detection has no operator-confirmed ground truth,
so a detector's false-positive rate cannot be measured directly against
known outcomes, only inferred, estimated, or left unstated.
`orbit-audit` is built for a reader who needs that rate measured, not
assumed, and who needs the specific published wording of a detection to be
traceable to a machine receipt.

Established work in this area demonstrates that manoeuvres can be recovered
from TLEs at all: @Kelecy2007 compared energy- and inclination-based
detection performance on individual objects, and @LemmensKrag2014 operated
threshold-based TLE manoeuvre detection at catalogue scale in low Earth
orbit. Both, and the population-scale work that has followed them, report
detections; neither carries a continuously recomputed, population-resolved
bound on how often the detector would flag an object with no manoeuvre to
detect. We are not aware of a prior public TLE manoeuvre detector that
recomputes a false-alarm bound on every run against a class-based negative
control and withholds its own detection vocabulary when that bound is not
cleared. That gate, and its self-reporting when it fails, is the
contribution `orbit-audit` makes available for reuse.

# State of the field

@Kelecy2007 and @LemmensKrag2014 established that TLE-derived
orbital-element residuals separate manoeuvring from non-manoeuvring objects
well enough to detect individual events, and @LemmensKrag2014 in particular
operated at catalogue scale. More recent work continues in that direction at
larger scale and with learned models: @Fu2026 reports physics-informed
learning for orbital-anomaly detection at 232 million element sets, and
@Guo2026 releases a manoeuvre-annotated LEO dataset (MAD-LEO) built from
tiered multi-source evidence. `orbit-audit` does not claim precedence of
scale over this work, and does not claim to be the first TLE-based detector
of any kind. Its point of difference is architectural rather than a claim
about detection accuracy: the false-alarm rate is a first-class, continuously
measured output of the pipeline itself, computed from a physically
motivated negative-control class on the same run that produces a detection,
rather than reported separately, estimated offline, or left to the reader to
infer from a validation study on a different dataset.

# Software design

The detection pipeline (`pipeline/orbit_events.py`, `pipeline/orbit_drift.py`,
`pipeline/orbit_campaigns.py`) builds per-object element-set intervals from
the archive, fits a nightly drift lane against a fixed decision rule, and
classifies flags by physical regime. The false-alarm control is implemented
in `pipeline/orbit_events.py`: the catalogue's passive population (debris and
spent rocket bodies) is measured as a negative control on every run, its
rate is reported as an equal-tailed Jeffreys credible interval
[@Jeffreys1946] rather than a point estimate — chosen because a Wald
interval collapses to zero width at zero observed flags — and a detection is
worded as a manoeuvre only when the payload population's lower bound clears
the passive population's upper bound by a pre-registered separation factor
recomputed on that run.

The drift-detection lane has paired CPU and GPU implementations
(`pipeline/orbit_drift.py`, `pipeline/orbit_drift_gpu.py`); the GPU path is
required for throughput at catalogue scale, and is checked for exact
numerical parity against the CPU reference implementation rather than
assumed equivalent (`tools/verify_orbit_sweep_gpu.py`;
`tests/test_orbit_drift.py`). Every figure published in the two research
papers produced with this software is regenerated deterministically by
`tools/make_figures.py` directly from committed artifacts under `docs/`,
with no random seed, no live re-measurement, and pinned PDF metadata, so
re-running the script twice against the same commit produces byte-identical
output. Each analysis is pre-registered before it is run: the hypotheses,
decision rules and stopping conditions live in `docs/*preregistration*.md`,
and the registration documents are hashed and anchored to the Bitcoin
blockchain via OpenTimestamps before the corresponding measurement, so a
result cannot be quietly rescoped after the fact without that rescoping
being externally checkable. The Python analysis and pipeline code is
exercised by an automated test suite of 681 tests
(`python3 -m unittest discover -s tests -p 'test_orbit*.py'`), five of which
are skipped without CUDA hardware present.

# Research impact statement

`orbit-audit` produced the analyses reported in two research papers released
alongside this software, each with an archived DOI: a registered,
population-scale test of geostationary end-of-life station-keeping folklore
[@Egan2026a], and the false-alarm-bounding apparatus itself, including two
registered stress tests the apparatus failed rather than passed silently
[@Egan2026b]. Both outcomes — the underpowered result in the first paper and
the failed stress tests in the second — are reported at the same prominence
as the positive results, because the software's stated purpose is to make a
detector's own limits checkable rather than to demonstrate that it always
succeeds. Given the software's recent release, its near-term significance
is that it gives SSA researchers and reproducibility auditors a working,
machine-checkable answer to a question the literature has so far mostly left
to detection-side reporting alone: how often would this detector flag an
object that could not have manoeuvred.

# AI usage disclosure

Generative AI coding and writing assistants were used during parts of this
software's development and in preparing this paper, under the authors'
direction; all such output was reviewed by the authors, who take full
responsibility for the content. The disclosure sentence carried by the two
accompanying research papers documents this same use for the analyses those
papers report (see their Acknowledgments sections). No AI tool or vendor is
named in this repository outside that disclosure; a repository-wide check
enforcing that (`tools/release_gate.sh`) runs before every release.

# Acknowledgements

This work received no external or third-party funding.

# References
