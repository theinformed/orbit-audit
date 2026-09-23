# T8 proximity/approach-detection track: adversarial prior-art sweep

Reviewed 2026-09-22, against `docs/proximity-results-20260922.md` (T8a, GEO,
discharged) and `docs/proximity-leo-preregistration-20260922.md` (T8b,
LEO/MEO/HEO, registered, no result yet). Modeled on the 2026-09-20 review of
the maneuver-detection track. Same discipline: absence of evidence is stated
as the limit of the search, never as a positive finding; no fabricated
citations; every citation below is either **verified** against a live source
fetched in this session or listed separately as an **unverified lead**.

**One-paragraph verdict.** Nothing found duplicates T8's specific combination
of scope (full public TLE archive, not a curated case list), discipline
(pre-registered thresholds, gates stated before the number existed) and
honesty (a null result and a falsified control reported as such). Individual
pieces are occupied — CSIS and SWF have been publishing curated GEO
proximity case studies for years, and the "debris as negative reference"
control idea is a granted patent — but no source found combines them into an
open, quantified, audited catalogue. That is a real gap, not an unclaimed
throne: it may be a gap because no one else has tried it at this discipline
level, or because it is genuinely hard to do openly (classification,
liability, access to a comparably deep archive). The sweep below cannot tell
which, and says so at each claim.

---

## Claim 1 — open, full-TLE-archive, pre-registered GEO approach-event catalogue (487 events): **UNCONTESTED AS FAR AS SEARCH SHOWS**

**Nearest work, and the daylight.**

- **CSIS Aerospace Security Project, "Unusual Behavior in GEO" data pages**
  (e.g. the Luch/Olymp-K page, fetched and read directly). Confirmed by
  direct read: this is a **single-object case study** (one satellite, July
  2017–December 2020, ~16 documented positions), not a systematic archive
  scan. It uses a fixed proximity threshold (0.075°, ~55 km, held ≥ 1 week)
  but the analysis is descriptive of one object's history, not the output of
  a detector run over the full catalogue. No lead-time measurement, no
  false-alarm rate, no chance-co-location null. CSIS runs a parallel page for
  SJ-17 (Chinese satellite, three RPOs against Chinasat 6B/SJ-20/Gaofen 13)
  — same shape: curated, per-object, not archive-scale.
- **CSIS, *Space Threat Assessment* (annual, 2019–2025)** and **Secure World
  Foundation, *Global Counterspace Capabilities Report* (annual)**. Both are
  explicitly aggregation/curation of open-source reporting on named events,
  organized by country and capability class, not detector output over a full
  element archive. Neither publishes an event-level dataset with reproducible
  thresholds.
- **AMOS pattern-of-life literature** — "Geosynchronous Satellite
  Pattern-of-Life Node Detection and Classification" (title/abstract found;
  full text blocked, see Unverified Leads), the MIT "Satellite
  Pattern-of-Life Identification Challenge" (AMOS 2024, a competition on a
  curated/simulated dataset, not the public archive), "Learning Satellite
  Pattern-of-Life Identification: A Diffusion-based Approach" (arXiv
  2412.10814). These build classifiers or generative models of behavior
  *classes*; none was found to publish a dated, thresholded, reproducible
  event catalogue comparable in scope to T8a's 217M-element-set scan.
- **COMSPOC / Oltrogge** (AMOS 2023, "Addressing the Debilitating Effects of
  Maneuvers on SSA Accuracy and Timeliness") characterizes how maneuvers,
  including RPO, degrade SSA accuracy — a different question (tracking
  quality, not an event catalogue). Title and venue verified; full text was
  not readable in this session (see Unverified Leads), so the specific
  overlap claim above is bounded by the abstract-level description only.

**Why UNCONTESTED rather than OCCUPIED:** every curated source found is
either narrower in scope (one object, one nation's activity) or answers a
different question (tracking degradation, behavior classification). None
was found to be (a) full-archive, (b) pre-registered before the numbers
existed, or (c) open with a reproducible event-level output.

**Search limits, stated as limits:** amostech.space's newer paper portal
returned 403/405 on several direct fetches (2024/2025 full-text PDFs); this
sweep relied on abstracts/snippets for those. COMSPOC's and ExoAnalytic's own
internal proximity-monitoring products are commercial and not independently
inspectable — their marketing pages claim continuous GEO monitoring but
disclose no methodology, event count, or open dataset, so they cannot be
placed on the OCCUPIED/ADJACENT/UNCONTESTED scale at all; they are noted here
as a category of claim that cannot be verified, not as absent competition.

---

## Claim 2 — measured early-warning lead-time distribution (median 36.1 d causal warning, 32.8% precision): **UNCONTESTED AS FAR AS SEARCH SHOWS**

No published quantification of a lead-time distribution for GEO
approach/RPO detection from the public element archive was found — neither a
median/percentile distribution nor a precision (alert-to-event hit rate)
figure, audited or otherwise. This mirrors the 2026-09-20 review's finding
for the EOL-prediction track (also "no population-scale quantification
exists"): the literature states the qualitative capability ("operators can
sometimes infer intent from element changes") but this sweep found no paper
or report that turns it into a number with a denominator.

The nearest *domain-adjacent* precedent is warning-time quantification for
asteroid-impact detection (median warning time and percentile span reported
in recent Vera Rubin Observatory studies) — a genuinely different physical
problem (discovery of an unknown object vs. re-detection of a change in a
known object's cataloged elements) and cited here only to show the shape of
a rigorous lead-time claim exists elsewhere in space situational awareness,
not as prior art on this specific claim.

**Forbidden framing consequence:** "first" cannot be claimed (absence of
evidence is not evidence of absence), but "first quantification located by
this search" is defensible and should be the actual phrasing if any claim of
priority is made at all.

**Search limits:** commercial SSA providers (LeoLabs, Slingshot, ExoAnalytic,
COMSPOC) advertise "early warning" and "predictive" capabilities in press
material; none of the marketing pages found disclose a lead-time
distribution, a precision figure, or a methodology sufficient to compare
against T8a's number. Classified/restricted literature (if any exists on
this exact question) is outside this search's reach by construction.

---

## Claim 3 — population-level null: GEO relocations land near other satellites ~2.2x LESS than chance: **UNCONTESTED AS FAR AS SEARCH SHOWS**

No published chance-co-location null test — permutation-based, analytic, or
otherwise — specific to GEO relocation behavior was found. General spatial
co-location statistics and permutation-test methodology are well established
outside this domain (e.g. co-location pattern mining in geospatial/pollutant
epidemiology literature), which is cited only to confirm the *method* (draw a
null from the empirical occupied-longitude distribution, permute, compare) is
a recognized general technique, not to claim any GEO-specific precedent for
the *finding*. The direction of the T8a result — relocations land near
occupied slots *less* than a naive draw from the occupied-longitude
distribution predicts, because objects relocate toward emptier slots for
ordinary operational reasons — was not found stated or tested anywhere in
the GEO SSA literature searched.

**Search limits:** this is precisely the kind of aggregate, non-newsworthy
negative finding that would not appear in curated threat-assessment
literature (CSIS/SWF cover *events*, not population-level nulls), and it is
also the kind of result an operator (COMSPOC, an insurer, a slot-coordination
body like the ITU or a satellite operator's own flight-dynamics team) could
plausibly have computed internally without publishing. Absence from open
search does not mean absence from practice.

---

## Claim 4 — audited false-alarm control on an approach detector (Paper B apparatus): **OCCUPIED at the idea level, ADJACENT at the application level**

This claim inherits the 2026-09-20 review's Claim 1 verdict directly, since
T8 states it reuses the Paper B apparatus. Restated and extended with what
this sweep adds:

**OCCUPIED:**
- **"Debris as negative reference" / no-maneuver baseline** — Raytheon
  patent US11649076B2 (2020/2023), reused from the prior review, trains a
  no-maneuver baseline on debris. T8a's registered passive-class control
  (DEBRIS, ROCKET BODY) is the same idea, applied to GEO proximity instead of
  general maneuver detection.
- **"Catalogue scale" as a claim** — Lemmens & Krag 2014 (JGCD, from the
  prior review) and **Fu, arXiv:2605.09790, "Multi-Tier Labeling and
  Physics-Informed Learning for Orbital Anomaly Detection at Scale"**
  (verified: Substratum Labs, LEO orbital-anomaly detection — maneuvers,
  decay, attitude upsets — framed explicitly as a prerequisite for collision
  avoidance and conjunction screening, at a stated ~232M-TLE scale per the
  prior review). This occupies the general claim "we processed a
  catalogue-scale TLE archive," which is why the prior review banned "first
  at catalogue scale" as a phrase — that ban applies here too.

**ADJACENT, with the daylight stated:**
- **MAD-LEO, arXiv:2609.08556** (verified by direct fetch): an
  evidence-tiered, cross-source-verified maneuver ground-truth dataset
  (1,134 annotated maneuver events from geodetic/altimetry satellites
  1992–2026, plus a 6,785-Starlink 107-hour tracking sample). It is
  **LEO-focused** and does **not** address proximity/approach-event
  detection, plane-matching, or lead-time/precision of an early-warning
  detector — it validates individual maneuver labels, not an approach
  detector's leak rate. This is the nearest thing found to "evidence-verified
  controls" for T8b's manoeuvre detector, and the gap the prior review
  already named (tiny N relative to catalogue scale) still applies.
- **What remains genuinely unclaimed**: a *standing, published, gating*
  false-alarm audit specifically for an **approach-event** detector — one
  that (a) runs a passive/never-manoeuvred control through the identical
  detector, (b) reports the control's leak rate against the same exposure
  denominator as the real population, and (c) reports the audit **firing**
  (control leaks at the same rate as the real population, i.e. the detector
  fails its own control) as a negative result rather than suppressing it.
  T8a's §7 (gate B fired, ratio 0.9995, 21x over its own bar) and T8b's §3.4
  redesign (manoeuvre-history-based control replacing `object_type`) are, as
  far as this search reaches, the only place this specific audit — applied
  to *approach/co-location* events rather than general maneuver detection —
  has been run and published with the failure reported rather than
  papered over. That is the real contribution, and it is narrow: not "audited
  false-alarm control" as a general idea (occupied), but "ran it on an
  approach detector and published the failure."

---

## Claim 5 — LEO plane-matching-campaign early warning (T8b, in progress, pre-registration only): **UNCONTESTED AS FAR AS SEARCH SHOWS, with one FALSE-FRIEND flagged**

T8b has not produced a result yet (registration only, per
`docs/proximity-leo-preregistration-20260922.md` §12: "nothing is committed
with this document" beyond itself). This verdict is therefore a
pre-registration check — is the *approach* novel — not a results check.

**False friend, must not be cited as prior art despite lexical overlap:**
**Soret, Leyva-Mayorga & Popovski, arXiv:1905.08410, "Inter-plane satellite
matching in dense LEO constellations."** Verified by search snippet and
abstract: this is inter-satellite-link routing/assignment optimization for
mega-constellations (which satellite in an adjacent plane to link to, to
minimize cost), not detection of an external object matching a target's
orbital plane. The phrase "plane matching" in T8's documents and this
paper's "satellite matching" refer to unrelated problems. A future T8b
write-up citing this paper as related work would be citing the wrong thing;
it is listed here specifically so no one does.

**Genuinely adjacent, not overlapping:**
- LEO maneuver-detection literature generally (Kelecy 2007's TLE algorithm,
  deep-learning TLE-prediction maneuver detectors, MAD-LEO) detects that *a*
  maneuver happened; none was found that assembles a **plane-matching
  campaign** (a multi-maneuver, weeks-to-months J2-exploiting RAAN closure
  followed by phasing) into a single attributable event with a lead time, the
  way T8b's §4–§5 registers.
- RAAN-drift rendezvous-planning literature (mission design: "wait for
  nodal drift to align planes, then execute") describes the physics T8b's
  §2.3 derives, but from the perspective of the maneuvering party planning a
  rendezvous, not a third-party detector inferring the campaign from public
  elements after the fact. This is the same relationship T8a had to
  satsig.net's "everyone knows GEO retirees relax station-keeping" folklore:
  the physics and the operational behavior are known: the population-scale,
  public-archive, causally-dated *detection and lead-time measurement* of it
  was not found published.

**Search limits:** T8b's own physics (§2.2–§2.5) is standard orbital
mechanics (Brouwer/Vallado-level), so "derived from first principles" is not
by itself a novelty claim and T8b's document does not make it one. The sweep
did not find, and did not expect to find, prior art for a result that does
not yet exist; this section should be re-run once T8b has a result, in the
same way T8a's own review would need re-checking against anything published
in the intervening months.

---

## Must-cite list

1. CSIS Aerospace Security Project, "Unusual Behavior in GEO: Luch
   (Olymp-K)" — https://aerospace.csis.org/data/unusual-behavior-in-geo-olymp-k/
2. CSIS Aerospace Security Project, "Unusual Behavior in GEO: SJ-17" —
   https://aerospace.csis.org/data/unusual-behavior-in-geo-sj-17/
3. CSIS, *Space Threat Assessment* (annual series 2019–2025) —
   https://aerospace.csis.org/space-threat-assessment-2020/ and successor years
4. Secure World Foundation, *Global Counterspace Capabilities Report*
   (annual) — https://www.swfound.org/publications-and-reports/2025-global-counterspace-capabilities-report
5. Secure World Foundation, "New SWF Publication Examines Risks and
   Opportunities of Rendezvous and Proximity Operations" —
   https://www.swfound.org/news/new-swf-publication-examines-risks-and-opportunities-of-rendezvous-and-proximity-operations
6. CSIS, "Dancing Lights in Space: How to Manage The Risks of Satellite
   Close Approaches in Geostationary Orbit" —
   https://www.csis.org/analysis/dancing-lights-space-how-manage-risks-satellite-close-approaches-geostationary-orbit
   (policy/qualitative precedent — cite to show the discourse exists, not as
   a quantified result)
7. Oltrogge et al., AMOS 2023, "Addressing the Debilitating Effects of
   Maneuvers on SSA Accuracy and Timeliness" —
   https://amostech.com/TechnicalPapers/2023/SDA/Oltrogge.pdf (venue/title
   verified; full text unreadable in this session, cite at abstract level
   only until re-verified)
8. Kelecy, T. et al., AMOS 2007, "Satellite Maneuver Detection Using
   Two-line Element (TLE) Data" —
   https://amostech.com/TechnicalPapers/2007/Modeling_Analysis_Simulation/Kelecy.pdf
   — foundational TLE maneuver-detection precedent, reused from the
   2026-09-20 review. **Reconciliation — RESOLVED 2026-09-22.** Fetched the
   primary PDF directly from amostech.com and extracted its text
   (`pdftotext -layout`). Both figures are genuinely in the paper; they
   describe two different results, not a contradiction:
   - The paper's headline, systematic result for Envisat (SSN 27386,
     inclination ~98.5°) — reached by "[r]epeating the detection level,
     polynomial window length and fit order cases examined for the Topex
     data ... then run on all of the data" — states verbatim: "an energy
     (fine-control) maneuver detection performance of 95% and a false
     detection rate of 6%. The process results in an inclination
     (orbit-control) maneuver performance of 85% and a false detection
     rate of 7%." (§4, text accompanying Figs. 10.a–b). This is the
     95%/6% vs 85%/7% figure this sweep flagged against the 2026-09-20
     review, and it is what the 2026-09-20 review and Paper B's citation
     ("roughly 95%/6% against 85%/7%, on objects at 66° and 98.5°")
     state — Topex's inclination is ~66° and Envisat's is ~98.5°, both
     confirmed in the paper's §2.
   - The "100%/0%" figure this sweep's search snippet surfaced is also
     real but is an earlier, narrower "best case" tuned-parameter
     demonstration on a single Envisat maneuver event (Figs. 9.c–d), not
     the paper's systematic/aggregate finding: "the inclination maneuver
     was easily detected at the 100% level with no false detections. In
     the case of the energy maneuver, 95% was the best-achieved detection
     reliability with a false detection level of a little over 6%." (§4,
     "Baseline Case: Best Case Detection and No False Detections").
   **Verdict:** the 2026-09-20 review's memory record and Paper B's Kelecy
   citation are correct and already cite the paper's actual
   systematic/aggregate result, not the narrower best-case illustration.
   No paper text required a change; this entry documents the check.
9. Raytheon, US Patent 11,649,076 B2 (debris-as-negative-reference /
   no-maneuver baseline) — reused from the 2026-09-20 review.
10. Fu, Y., arXiv:2605.09790, "Multi-Tier Labeling and Physics-Informed
    Learning for Orbital Anomaly Detection at Scale" —
    https://arxiv.org/abs/2605.09790
11. MAD-LEO, arXiv:2609.08556 —
    https://arxiv.org/html/2609.08556
12. NASA CARA program — https://satellitesafety.gsfc.nasa.gov/CARA.html and
    the 2025 FAQ/handbook (cara-faq-npr-handbook-2025.pdf) — must-cite to
    state the collision-safety-screening vs. intent-pattern-warning
    distinction explicitly (CARA screens for miss distance and collision
    probability on a fixed cadence; T8 detects and dates *intent-shaped
    changes* in elements — different estimand, different consumer).
13. Roberts, AMOS 2021, "Geosynchronous satellite maneuver classification
    via supervised machine learning" —
    https://amostech.com/TechnicalPapers/2021/Machine-Learning-for-SSA-Applications/Roberts.pdf

## Forbidden phrasings

- **"First open catalogue of GEO approach events"** / **"first at catalogue
  scale"** — reused ban from the 2026-09-20 review; CSIS/SWF/Fu/MAD-LEO all
  occupy pieces of "catalogue scale" or "open GEO event documentation" even
  though none occupies the combination. Say "the only one this search
  located" or scope it precisely (e.g. "the only full-archive, pre-registered
  GEO approach catalogue located by this search").
- **"Proves operators avoid proximity" / "shows deliberate avoidance"** for
  Claim 3 — the 2.2x-below-chance null is a population-level association
  (relocations tend toward emptier slots because objects need a slot they
  can occupy), not evidence of intentional avoidance behavior. No intent
  claim is licensed by this number.
- **"First quantification of early-warning lead time"** — say "first
  quantification located by this search" instead; classified/proprietary
  work may exist and cannot be ruled out (Claim 2's search-limits paragraph).
- **"Audited false-alarm control"** used as a bare, general phrase — always
  scope it to what was actually audited (an approach-event detector against
  a manoeuvre-history-based control, reporting the leak) — the general idea
  is occupied (Claim 4); only the specific application and the published
  failure are not.
- **"Novel plane-matching detection"** without disambiguating from
  Soret/Leyva-Mayorga/Popovski's inter-plane satellite *matching* (ISL
  routing) — same words, unrelated problem; a reviewer who knows that paper
  will assume conflation unless T8b's write-up distinguishes it explicitly.
- Any **intent/threat vocabulary** (inspection, spying, threat, adversary,
  hostile, shadowing, stalking) — already self-banned by T8a/T8b's own
  registration language; restated here because it is also what separates T8's
  claimed contribution from the CSIS/SWF literature, which *is*
  intent-laden. That framing difference is a legitimate point of departure
  to state plainly (T8 is ownership-agnostic mathematics; CSIS/SWF are
  named-actor threat narratives) — it is not evidence that T8's numbers are
  more correct, only that they answer a different, narrower question.
- **"Validated" applied to T8b's dwell bound, control, or any §10 gate**
  before the corresponding gate (G, H, B′, etc.) has actually been run
  against data — T8a's own §7.2 is the cautionary example (a derived bound
  was asserted as conservative and was falsified 5/5 when checked).

## Search-coverage statement

**Searched:** general web search (WebSearch) across AMOS conference
proceedings (amostech.com, amostech.space, ADS abstracts), COMSPOC/Oltrogge
publications, CSIS Aerospace Security Project (including direct fetch of two
"Unusual Behavior in GEO" pages and the Space Threat Assessment series),
Secure World Foundation Global Counterspace reporting, arXiv (RPO/TLE
detection, maneuver anomaly detection, inter-plane matching, Russian-activity
anomaly detection), NASA CARA program documentation, and general spatial
co-location/permutation-test methodology literature as a method-only check
for Claim 3. Direct WebFetch reads were performed on: the CSIS Luch/Olymp-K
data page (successful, full methodology read), the CSIS "Dancing Lights in
Space" page (successful), the MAD-LEO arXiv abstract (successful), and
several AMOS technical-paper PDFs (Oltrogge 2023, Serrano 2024) which
**returned unreadable/garbled binary content** through the fetch tool and
could not be verified beyond their title/venue/search-snippet level — these
are listed above as verified-at-title-level only, not verified-at-methodology
level.

**Not reachable / not verifiable in this sweep:**
- Several amostech.space 2024/2025 full-text pages returned HTTP 403/405.
- ResearchGate's "Geosynchronous Satellite Pattern-of-Life Node Detection
  and Classification" page returned 403.
- Commercial SSA-provider methodology (COMSPOC, ExoAnalytic, LeoLabs,
  Slingshot Agatha) is disclosed only at the marketing/press level; none
  publishes a peer-reviewable methodology, event count, or open dataset
  comparable to what would be needed to place their claims on the
  OCCUPIED/ADJACENT/UNCONTESTED scale. Slingshot's Agatha (DARPA-backed) was
  checked specifically because it was named in the task brief: it is a
  behavior-anomaly/intent-inference system (inverse reinforcement learning
  over communication patterns), trained on simulated data, not a
  TLE-archive approach-event detector — different apparatus, not directly
  comparable to T8, and its claims are press-release level, not
  peer-reviewed.
- Paywalled journal content (Acta Astronautica, JGCD) was assessed via
  search-result abstracts/snippets only, not full text, except where the
  2026-09-20 review had already verified a specific citation.
- One arXiv paper found in-scope (2509.00050, Russian-satellite
  anomaly-detection-for-military-indicators) was found to be **withdrawn by
  its authors for inaccurate information and misrepresented findings** — it
  is not cited above and should not be cited by T8 either; noted here so it
  is not independently rediscovered and cited without the withdrawal being
  known.
- Classified, ITAR-restricted, or paywalled defense-industry literature is
  outside this search's reach by construction; its absence from this sweep
  is a limit of the search, not a finding that it does not exist.

## Unverified leads (not cited as confirmed precedent above)

- "Geosynchronous Satellite Pattern-of-Life Node Detection and
  Classification" (ResearchGate 368923741) — title/existence found, content
  blocked (403).
- Oltrogge et al., AMOS 2023 (item 7 above) — title/venue verified, full
  methodology not independently read.
- Serrano et al., AMOS 2024, "Monitoring of Rendezvous & Proximity
  Operations With SST and SDA Techniques Combination" — title/venue/ADS
  abstract link verified; PDF fetch returned unreadable binary content, so
  scope, scale, and whether it reports a lead-time or precision figure could
  not be confirmed. Flagged for re-check before any claim about "the only
  other RPO-monitoring paper combining SST+SDA" is made.

## Bottom line

T8's five claims survive this sweep in roughly the shape the task expected:
the open/full-archive/pre-registered/audited *package* is not found
anywhere else, and three of the five claims (1, 2, 3) are population-level or
distributional results this search found no precedent for at all — stated as
a search limit, not a proof of originality. Claim 4 is the one with real
prior art to cite and disclaim carefully: the control-population idea is
patented and the catalogue-scale-processing idea is published; what is not
found published is the specific audit run on an approach detector with its
failure reported. Claim 5 has no result yet and one important false-friend
citation to avoid when it does.
