# The "oh wow" assessment — what in this programme would make an expert sit up, and what would not

Written 2026-09-22 by a reviewer asked to be honest rather than generous. Scope: the
track roster in `docs/research-program-runbook-20260921.md` (T1–T18 and its STATUS
section), the two published papers, and the results documents named in each row.
Method: read the programme first, then survey the open literature; every judgment below
names what was opened and what was only seen at abstract level.

**Standing caveat on every "nobody has done this" here.** Absence from an open-literature
search is a limit of the search, not a proof of originality — and §2's first row is a worked
example of that caveat biting. Where I write NEW I mean *not located*, nothing stronger.

---

## 1. The one-paragraph reading

This programme's centre of gravity is not a discovery. It is a **measurement culture**:
registrations committed alone before instruments exist, controls that are validated
before they are used, gates that are allowed to fire, and numbers that are refused when a
leak check fails. That is rare in this field and it is the thing most likely to be
remembered. Against that, the substantive astrodynamical findings are mostly (a)
re-derivations of textbook physics demonstrated at population scale, (b) honest negative
results, or (c) properties of the programme's own detector rather than of the sky. Four
exceptions are worth the field's attention: the published covariance of a megaconstellation
turning out to be a hand-set constant over most of its span; the physical demonstration
that the geostationary belt admits no leak-free passive control; measured early-warning
lead-time distributions where the field has only anecdotes; and a parameter-free reading of
burn direction off slot geometry. Only the first is worth anyone's money today, and the
programme's own highest-value financial target — an externally-observed propellant bound —
is real, unoccupied, and currently out of reach.

### 1.1 The short answer

**Top three for a satellite / astrodynamics / SSA expert**

1. **A megaconstellation's published covariance is a hand-set constant over most of its
   prediction span** — four to five distinct values across 246 files at 72 h, and a 48 h
   in-track sigma *smaller* than the 24 h one. **Independently replicated during this
   review at larger scale** (§2), and it lands in a documented hole: no standard requires
   an operator covariance to be realistic, no body validates one, and the single
   peer-reviewed study of these files reads their covariance as if it were measured
   accuracy.
2. **The geostationary belt admits no leak-free passive control, and the reason is physics**
   — a stationed passive object is a free librator at its turnaround, and a librator at its
   turnaround is a slow approach that dwells, which is exactly the shape an approach
   detector is built to find. A whole class of detectors cannot be validated the way their
   low-orbit counterparts can. This is undersold in the programme's own write-up.
3. **Burn direction read off slot geometry with no free parameter, 91 of 91.** Textbook
   physics, but a clean parameter-free demonstration that the archive carries real burn
   structure — and the per-object sign kills every artefact explanation at once.

*Runners-up, and the first of these is close to the podium:* **measured early-warning
lead-time distributions where the field has only anecdotes** — two independent sweeps found
no published lead-time distribution for approach detection at all, against a best public
anecdote of roughly ten days for one named event pair; the never-manoeuvred low-orbit
control returning exactly zero events over 18.8 million object-days; and the alarm's own
denominator correction from 32.8% to 0.103%.

> **CORRECTION, and it matters.** An earlier version of this assessment put the measured
> recall (7.94%) first, on the reading that no population recall against operator-published
> manoeuvre truth had been published. **That reading was wrong.** Recall against
> mission-published manoeuvre histories has been published repeatedly, on the same
> spacecraft — see the first row of §2. The recall measurement remains valuable *inside*
> this programme, and the honest reading of it is considerably less flattering than a first.

**Top three for a space-insurance or finance expert: two, and the second one is a target
rather than a result.**

1. **The constant covariance columns.** A data-governance fact in a safety chain, not a
   rating input — but with a ready-made hook: a senior underwriter has already co-authored
   the caveat in print ("In reality, the P<sub>C</sub> is either 0 or 1; the P<sub>C</sub>
   value merely represents our confidence as to which outcome is likely to occur").
2. **Remaining propellant, as a target.** The prize is quantified — deferring a large
   geostationary replacement is worth **$20–32 M per year** against a ~$300–350 M
   replacement, and life-extension has been sold at ~$13 M/year — and the lane is verifiably
   open: **no published method estimates remaining propellant from purely external
   observation.** Every existing technique needs on-board telemetry. This programme's bound
   is the right idea aimed at the right gap and is currently far too weak to use (§3).
3. **A distant third:** close-approach base rates for in-orbit-servicing and
   proximity-operations cover — narrow, growing, and with almost no empirical base rate.

---

## 2. What a satellite / astrodynamics / SSA expert would say

Verdict key: **NEW** = not located in the literature; **INCREMENTAL** = known in
direction, quantified here; **KNOWN** = textbook or standard practice.

| Finding | Status vs literature | Would an SSA expert say "oh wow"? | What survives scrutiny / what does not |
|---|---|---|---|
| **Measured recall of the shipped detector: 7.94% [6.50, 9.66] over 1,134 operator-reported burns; 977 of them below the detector's own 102–126 m semi-major-axis floor; 51.6% above the floor vs 0.9% below; 26× placebo lift; campaign-level 1.32%** (T16b) | **NOT NEW as a genre, and this is the single most important correction in this document.** Recall against mission-published manoeuvre histories is published repeatedly, on the same spacecraft: **Kelecy et al. (AMOS 2007)** against NASA manoeuvre-history truth — TOPEX 6/6 with zero false detections when tuned, Envisat 95%/6% energy and 85%/7% inclination (recounted by Decoto & Loerch as 49/78 = 63% over the wider window); **Decoto & Loerch (AMOS 2015)** — all 8 ESA-reported Envisat manoeuvres from public elements with 2 false positives, and 2 of 4 known Intelsat burns at GEO; **Cipollone, Raviola & Di Lizia (ESA SDC9, 2025)** — full precision/recall/F1 against operator histories: Sentinel-3A recall 1.000, Sentinel-3B 0.986, CryoSat-2 0.63–0.85, Envisat 0.35–0.64; **Shorten et al. (JSR 2022 / Acta Astronautica 2025)** — a released 15-satellite ground-truth benchmark, largely the *same* spacecraft, with threshold-swept precision–recall curves. MAD-LEO itself publishes a ~24 m element-set noise floor and a median real response of 20.3 m. | **NO — and the honest reading runs the other way.** Against published recalls of 0.35–1.00 on these very spacecraft, 7.94% is a **low outlier**, and the programme's own documents say why: the shipped threshold is set by a population-median noise term 130–470× coarser than these well-tracked objects' own noise. What this measured is the calibration of one shipped detector, not a property of the observable. The per-object-noise arm (7.94% → 11.29% at an unchanged labelled-quiet count) confirms it. | **Survives:** the floor derivation, the split at the floor, the placebo control, the per-spacecraft burn-size table, and — as an internal engineering result — the finding that the shipped threshold is mis-set for any well-tracked object. **Does not survive:** "the programme's first measured recall" is fine; "the first public recall figure" is false and must not appear in Paper B, in the runbook, or anywhere else. Any publication must place 7.94% beside the published figures above, or a referee will do it for them. |
| **Starlink public ephemeris covariance: at 72 h lead only 4–5 distinct values across 246 files (300 m / 3,800 m / 500 m, round numbers); 48 h in-track median *below* the 24 h one; usable range 0–12 h where formal in-track σ runs 0.88 m → 804 m** (T16a §6) | **NEW, and the surrounding evidence is stronger than the programme knows.** The files have been studied for accuracy — overlapping-file self-consistency across ~1,500 satellites (arXiv:2510.11242, opened) and next-element-set-as-truth comparisons (arXiv:2605.19850, opened) — but both *use* them and neither audits the covariance. Covariance realism is a mature method (Park et al., LeoLabs, AMOS 2019, opened) applied by providers to **their own** data. Three primary sources say the gap is real and known to be unfilled: NASA's *Conjunction Assessment and Collision Avoidance Best Practices Handbook* (SP-20230002470 Rev 1, 2023) states that for covariances in operator ephemerides "the situation is much more uneven" and that "there are few published studies on the subject and no practical guides"; the 19th Space Defense Squadron writes in print of "the **inconsistency of O/Os providing realistic covariance (or covariance being omitted entirely)**" and that the data "is not officially validated by DoD standards" (Ramos et al., AMOS 2023); and the operator handbook says operators "**may elect** to include covariance data", with no realism requirement, no validation step and no rejection criterion. The forthcoming civil traffic-coordination format makes covariance mandatory but asks only that it be "expected to be scaled appropriately" — the word *realism* does not appear in it. | **YES — now clearly the strongest item in the programme.** A third party screening against these files is doing arithmetic with a constant over most of the prediction span. **Replicated independently during this review, at far larger scale:** over 11,137 live files, the covariance grows smoothly for the first hours, then snaps to an exact round-number plateau at a median of 27.3 h and holds it; across 120 independently sampled satellites there are only **10 distinct terminal triples**, and **74 of 120 (62%) share the identical (300, 3800, 500) m** — the same triple the programme measured. And the one peer-reviewed study of these files quotes their covariance as measured accuracy ("better than 2 km in the first day"), numbers that map onto the canned plateaus: a citable instance of the literature mistaking a default for a measurement. | **Survives**, and more robustly than the programme's own 250-file sample would support on its own. **Must still be hardened:** a multi-month census of distinct values by lead; the word *formal* throughout, because nothing validates the short-lead values either; and an explicit statement that this is about the published uncertainty, not about the ephemeris being wrong. **Correction to an earlier hedge in this document:** I previously allowed that screening organisations might routinely check operator covariance realism and simply not publish it. The primary sources say the opposite — nobody tests it, and NASA says so in as many words. The finding is stronger, not weaker, than first written. |
| **Burn direction set by slot side: a single 180°-periodic sign function of longitude separates the two phase modes 91/91 with no free parameter; permutation exceedance 0/2000; differenced-series skew agrees 111 times with zero disagreements** (T5a harmonic mechanism) | Physics is **KNOWN** and textbook — Earth triaxiality, two stable (~75.1°E, ~105°W) and two unstable equilibria, drift acceleration changing sign every 90°, is in every GEO operations text and in the classical literature on triaxiality-driven east-west keeping. The *empirical population demonstration from public elements, parameter-free*, was not located. | **A qualified yes — "nice", not "wow".** An astrodynamicist's first reaction is "of course". The second reaction is the useful one: it is a clean, parameter-free falsification test that the harmonic structure in the archive is real burns and not pipeline artefact, and it kills every common-cause explanation because the sign is per object. | **Survives:** the per-object bimodality of ψ₂ against unimodal ψ₃, the injection-recovery floor/ceiling, the 2.16 d bound on archive smoothing. **Does not survive:** the slot arm is explicitly post hoc; 47% of carriers have no readable per-object phase and a selection effect toward strong-harmonic objects is plausible and unmeasured; a sign function is not a dynamical model. Registered replication on an independent object set is mandatory before this is a claim. |
| **Audited, publicly gated false-alarm control that publishes its own fired gate — ~89 M passive intervals as a class-based negative control, bound-vs-bound separation, gate shut twice (8.83× matched composite, 5.36× full-archive reweighted, against a 10× bar)** (Paper B, T1) | The component ideas are **OCCUPIED**: debris-as-negative-reference is patented (US11649076B2); catalogue-scale TLE processing is published (Lemmens & Krag 2014; Fu arXiv:2605.09790). The *standing, gating, self-shutting* audit was not located, and **two independent sweeps agree that pre-registration and published false-alarm auditing are essentially absent from astrodynamics**. The nearest precedent found is a NASA science mission declaring its significance and power levels ex ante — with no post-hoc audit of whether the realised error rates matched. | **Yes, but slowly** — it is an infrastructure "oh wow", the kind that is admired at the second reading. The part experts will actually notice is that the authors shut their own gate and published the failure at abstract prominence. | **Survives** as a protocol contribution. **Does not survive** as a result: a shut gate is not a finding about the sky, and a referee may read the whole apparatus as overhead. The honest framing is "here is how to report a detector", not "here is what we found". |
| **GEO relocations land within 0.1° of another satellite 2.2× LESS than chance (observed 1,091 vs null 2,386 [2,203, 2,589], 1,000/1,000 permutations)** (T8a §6) | Not located, and a second independent sweep agrees: **no aggregate chance-baseline test of where geostationary relocations end up exists**. The nearest recent study of relocation behaviour (Rao & Szumilo 2026 — *unverified, snippet level*) carries **no random baseline at all**. | **Mild.** Useful as a public counterweight to proximity-alarm narratives. | **Does not survive** hard questioning about the null. Drawing an arrival longitude from the *occupied* longitude distribution asks whether satellites move to occupied slots — and they cannot, because an occupied slot is occupied. The result is close to arithmetic about slot availability. Publish it as a caution, never as behaviour. |
| **LEO co-orbital campaigns: median causal lead 195.9 d at 44.1% precision, with a never-manoeuvred control returning exactly zero events over 18,792,698 object-days** (T8b) | **Confirmed NEW by two independent sweeps: no published lead-time distribution for approach detection exists.** The public state of the art is anecdotal — the best-documented forewarning of a named geostationary approach is on the order of **ten days**, for a single event pair. Against that, a measured distribution (36.1 d median at GEO, 195.9 d in low orbit, with precision and censoring stated) is a genuinely different object. The never-manoeuvred control is the strongest in the programme. | **Yes on both, now.** Zero over 18.8 M object-days is a number a referee respects immediately, and a distribution where the field has only anecdotes is the clearest open lane the programme has after the covariance work. | **Survives:** the control, the J2 chance-co-planarity null, the CPU-beats-GPU measurement. **Does not survive:** the lead time is for *in-track phasing inside an already-shared plane* only — the registered plane-noise statistic measured sampling irregularity, not fit noise, and switched the plane channel off at 3.5°. That qualification must travel with the number everywhere, and it substantially narrows what was claimed. |
| **Trigger-time alarm: the real denominator is 97,784 firings, not 1,483 — 0.103% [0.085, 0.125] precision; best reproducible class 3.41% [2.37, 4.88], 45× lift, 22.1 d median lead, ~25–30 alerts/yr; tightening the evidence dial does NOT raise precision (3.410 → 2.681 → 2.725%)** (T8d, alarm build) | The self-correction has no analogue I located; commercial "early warning" claims publish no denominator at all. | **Yes, among methodologists.** "Our own design document quoted a precision that required the event to have already happened" is the most instructive paragraph in the programme. The dial finding — tighter is not more precise — is a genuinely useful operational fact. | **Survives** completely, because it is a correction downward. **Does not survive** any attempt to sell 3.41% as a product (see §7). |
| **1,317 tandem episodes over 239 GEO pairs inside a derived 0.0417° box; 93.9% carry a confirmed drift change on *both* members inside the episode; matched 14.00 d cadence phase-lock 44.1% vs 27.7% in 24,669 control pairs** (T11/T11b) | GEO co-location is **KNOWN** practice (Soop; eccentricity/inclination separation strategies). An open, population-scale catalogue of pairs with *positive evidence of active keeping on both members* was not located. | **Moderate yes.** The phase-lock statistic is the interesting part: it is evidence of *coordinated* control read off public elements. | **Survives:** the derived (not chosen) thresholds, the 93.9% positive-evidence re-expression, the arrival-order distribution (median gap 579 d — these are not co-launched pairs). **Does not survive:** the response hazard, correctly NOT READ; and the pairs remain geometry-plus-evidence, since GEO has no leak-free control (below). |
| **GEO has no leak-free passive control, and the reason is physics: a stationed passive GEO object is a free librator at its turnaround, which is itself a slow approach that dwells** (T11b part 2) | Not located as a stated result. | **Yes — this is a real methodological finding, undersold in the programme's own write-up.** It says a whole class of GEO detectors cannot be validated the way LEO detectors can. | **Survives**, and it is the most quotable negative result here. It also caps every GEO claim in the programme at "reported, not claimed", which the documents accept. |
| **LEO forward error vs precise orbits: median along-track 0.32–0.69 km at +1 d, 90–99 km at +30 d, 844–876 km at +90 d; growth quadratic (t^1.95–2.06); error 68–160× the radial** (T16b A) | **INCREMENTAL.** Along-track dominance and superlinear growth are long established (Vallado; Kelso; ESA assessments), and a contemporaneous megaconstellation study reports its own curve (arXiv:2605.19850, opened: SGP4 0.94 km at 6 h, 2.60 km at +1 d, 38.5 km at +7 d pooled over 24,641 pairs). | **No.** It is a good, honest, well-framed calibration against genuine precise orbits — three spacecraft, one year. | **Survives** as a calibration with its scope stated. **Does not survive** as a catalogue-wide statement: three cooperative, heavily tracked spacecraft are a best case, and the programme says so. |
| **14.00 d east-west cadence line on 208 GEO carriers → deadband ±0.021°, independently recovered at 0.0203° [0.0188, 0.0212] by a cycle-resolved estimator** (T3, T10c) | **KNOWN, and specifically published — including the inference from public data.** 7- and 14-day cycles are standard practice; beyond that, **Decoto & Loerch (AMOS 2015)** recover a 14-day best-fit cadence for a named geostationary comsat from public elements alone by a frequency scan over 8–65 days; **Pastor et al. (ESA SDC8, 2021)** report 14 days as the **modal** manoeuvre interval across **1,707 geostationary objects**, with secondary peaks at 7, 21 and 28 days; and **Siew et al. (AMOS 2023)** publish both the cadence (14-day north–south, 11–18-day east–west on a named satellite) **and deadbands read off element-derived longitude histories** — 0.05°×0.05° for an electric bus, 0.1°×0.08° for a chemical one. | **No — and less than I first thought.** Every component of this result, including the deadband inference, is in print. | **Survives** as instrument validation, and the two-independent-estimators agreement is genuinely reassuring. **Does not survive** as discovery — and the registered per-object test was NULL (0/7,884 payloads), the window-level threshold failed to transfer three times with the *passive control firing above the treated class* (7.3%/9.4% vs a 1% nominal). A hostile referee will start there, and should. |
| **North–south 14.00 d inclination line on 56 named comsats at 15.85× local background** (T3 S1) | Not located; north–south keeping on the east-west cycle is plausible operationally. | **Mild interest.** | **Does not survive** as stated: two registered predictions failed (latitude-box periods absent; eccentricity did not corroborate), the implied ±0.0163° box is one several carriers demonstrably do not fly, and the same-regime control has an expected count below one window. Descriptive at best. |
| **Whole-history coherent stacking raises separation 11.07×/window → 115.01×/object, while both prescribed matched-filter template families are falsified** (T5a redesign) | Internal to the programme's own detector line. | **No** — but the *negative* result is well executed and the cross-validation to four significant figures against the earlier instrument is the right way to license a verdict. | **Survives** only with the stated caveat: no injection-recovery, no recall arm, no null, no p-value, and the confirmatory experiment is registered but unrun. Until it runs there is no claim. |
| **Manoeuvre library v1: 3,914,621 burns typed; only three types earn a confidence (0.68 / 0.56 / 0.55); the GEO inclination clause is measuring lunisolar motion, not burns; "orbit lower" leaks 13.96% on passive objects vs 4.71% for its mirror type, so the asymmetry measures drag** (T13) | **OCCUPIED.** Roberts & Linares (AMOS 2021 + MIT thesis) classify geostationary longitudinal-shift manoeuvres from public elements with published confusion matrices (recall 65–98%, precision 12–51%, on labels made by inspection); Roberts et al. (AMOS 2023) cluster **918 geostationary satellites over 2010–2021** into 24 behavioural modes correlated with propulsion type and bus age; Siew et al. (AMOS 2023) released a labelled pattern-of-life benchmark scored on precision and recall; recent work continues (Remote Sensing 2025). | **No** for the taxonomy. **Yes, quietly,** for the confession that a headline clause tests element-set spacing rather than burns, and for the drag-vs-burn leak as a *measurement* of the atmosphere. | **Survives:** "agreement between rule sets, never accuracy" is the right word and should never be relaxed. **Does not survive:** anything read as a manoeuvre census. |
| **Transfers are near-optimal: median path loss 0.340% over 58 multi-burn transfers; detector price audit shows the shipped price at a median 0.942 of the exact minimum with a maximum of 93.4×** (T10a) | **INCREMENTAL.** "Industry transfers are close to optimal" is expected; the derivation that successive tangential burns at the same apsis telescope exactly is textbook. | **No.** | **Does not survive** as a number: reported and explicitly not claimed, endpoint coverage thin (24 of 58 against a registered minimum of 30), electric arm empty at n = 0. The 93.4× price audit is an internal defect finding, not a field result. |
| **North–south burns placed a median 22° off node = 5.2 of a 45.6 m/s/yr budget; ~49% of the placement explained by inclination-vector drift management** (T10b) | A per-operator placement-efficiency figure was not located. | **Potentially yes** — operators and bus manufacturers would read a real off-node placement distribution with interest. | **Does not survive** in its first form: the bus-family ordering, which was the interesting claim, is **withdrawn** at permutation p = 0.32; the outcome is C-PARTIAL, missing its own bar by 0.13°; the median is reported and not claimed. What survives is the retrograde-Laplace-sense correction, confirmed three ways, which is a genuine physics fix. |
| **Deadband width cancels exactly from the annual east-west ΔV; a tighter box costs manoeuvre count as R^(−1/2), not propellant** (T10c) | **KNOWN** — it falls out of the standard triaxial drift relations. | **No.** | **Survives** as a clean derivation asserted to machine precision, and it is worth stating plainly because the folk belief runs the other way. The detected ledger shows no dependence on triaxial acceleration and the observed positive deadband slope is the detectability confound the registration named in advance — so nothing licenses "a looser box costs more fuel". |

---

## 3. What a space-insurance or finance expert would say

**Honest headline: for most of this programme, nothing.** Space insurance today prices
launch, early-orbit and in-orbit *spacecraft failure*. Collision and debris exposure is
handled largely by exclusions and aggregate limits rather than by a modelled collision
probability, and the market's recent stress has come from a handful of large
total-loss claims, not from collisions. An underwriter has no place to put a covariance
matrix. Three items are exceptions, and only one of them is ready.

Four opened primary sources say so directly:

- **OECD/ESA (Undseth, Jolly & Olivari, ESA Space Debris Conf. 2021):** "Space debris
  collisions have historically been considered low-probability and **not affecting insurance
  premiums**." Same paper on why: "the number and nature of objects recorded in existing
  debris catalogues **do not reflect the reality**", and operators lack the knowledge "to
  calculate and fully address technical and commercial risks."
- **A major underwriter's own paper on collision risk** (Kunstadter, AXA XL, ESA 2021):
  **fewer than one active satellite in ten carries in-orbit cover** (~6% in low orbit, ~43%
  in geostationary); framing "Debris risk? No… Collision Risk!"; and every recommended
  remedy is an **observability** one — beacons and trackers on everything, avoidance
  propulsion, disposal, servicing. Covariance, collision probability and catalogue accuracy
  appear nowhere.
- **An industry market report (Aon, Q1 2026)** gives the economics — 2023 claims ~$1.43 bn
  against ~$550 m premium; 2025 premium >$650 m against ~$503 m claims — and across twenty
  pages **never mentions debris, collision probability, conjunction assessment, congestion
  or space-surveillance data as a pricing consideration**. Cover is all-risks with few
  exclusions; where the risk became unbearable one carrier **left low orbit** rather than
  write an exclusion.
- **But the hook exists, and it was written by an insurer.** In a joint paper with a
  commercial radar operator (IAC 2022), the same AXA XL underwriter co-authors: "**In
  reality, the P<sub>C</sub> is either 0 or 1; the P<sub>C</sub> value merely represents our
  confidence as to which outcome is likely to occur**", and notes that radar-derived
  conjunction messages **overestimate** collision probability relative to satellites
  carrying navigation receivers.

That last item is the bridge. The gap between an underwriter who knows in print exactly how
soft the probability is, and a market that prices none of it, is the reviewable finding —
and it is documented in sources the same person co-wrote. A pitch to this audience must
start there rather than argue with the first three.

| Finding | Would a finance/insurance expert say "oh wow"? | What they would actually do with it | Honest limiter |
|---|---|---|---|
| **The constant 24 h / 72 h covariance columns in a megaconstellation's public ephemerides** | **Yes — the only unambiguous one.** It is not a pricing input; it is a *diligence and governance* fact about the data underneath collision-avoidance decisions made hundreds of thousands of times a year. | A reinsurer's emerging-risk team writes an internal note; a broker uses it in a data-quality question to an operator; a regulator or space-traffic-management policy shop cites it. The realistic bridge is the insurer-co-authored statement that collision probability "merely represents our confidence", plus the one narrow existing precedent of a commercial radar operator's risk tool built with an underwriter and described as useful for "setting space insurance rates" — though a rival underwriter is on record discounting it, saying better collision assessment "might not have a big impact on the price". A widely recycled trade-press claim that a syndicate and a carrier now grant deductible waivers for sharing high-fidelity tracking data **could not be traced to any insurer publication and must not be cited** until it is confirmed directly. | Nobody re-rates a policy on this. It must be hardened first (§5), and it must not be described as showing anyone's data is *wrong* — only that at long lead it is not a propagated uncertainty. |
| **Remaining-propellant / fuel-odometer bound (Paper A), and the manoeuvre-efficiency work (T10)** | **Not yet — but the target is now priced, and the lane is verifiably open.** Deferring a large geostationary replacement is worth **$20–32 M per year** against a ~$300–350 M replacement; life extension has been sold at ~$13 M/year; on-orbit propellant has been quoted near $200 k/kg. Fuel is documented as entering **financing** diligence — capital providers backing satellite projects are on record as concerned with "fuel budgets" — and depreciation models are said to break down where "asset longevity is determined by fuel reserves". **And no published method estimates remaining propellant from purely external observation**: every technique in the literature needs on-board telemetry (tank gauging, bookkeeping, thermal, moment-of-inertia). The nearest external work recovers ΔV *spend*, never inventory, and makes no financial claim. | Nothing today — but this is the right target, and the precision that would matter is knowable: on-board methods are reported near ±10–15 kg where operators want ±1 kg, and on the figures above roughly a year of geostationary life is $20–32 M. | Detected station-keeping ΔV is a median **1.81%** of the north–south budget, electric station-keeping is invisible to a step detector entirely, and the measured recall (7.94%, 1.32% at campaign level) confirms the scale of the miss. A bound that weak cannot distinguish a satellite with two years left from one with ten. Until recall moves by an order of magnitude this is not an underwriting input and must not be offered as one. Two further cautions: loss databases **under-record** this risk (the decade's two largest geostationary break-ups were uninsured, so neither produced a claim), and electric propulsion — the growing share of the fleet — is exactly where the odometer is blindest. |
| **The approach/tandem catalogues (T8a, T8b, T11): base rates of close approach, 1,317 tandem episodes, 93.9% proven keeping, and the 195.9 d / 36.1 d lead times** | **Potentially, for one narrow line of business: in-orbit servicing and proximity-operations cover.** An underwriter writing a servicing mission has almost no empirical base rate for how often objects come close and what happens next. | Sizing an RPO/servicing policy; arguing aggregate exposure in a crowded GEO slot. | The lead times are conditioned on the initiating burn being *detectable*, so they describe the detector as much as the behaviour; GEO has no leak-free control; and the response hazard — the actual question an underwriter would ask ("does the incumbent then move?") — is correctly **NOT READ**. |
| **The behavioural alarm at 0.103% (3.41% best class)** | **No.** | Nothing. | A 3.41% hit rate with a 22-day median lead is below any threshold at which a financial decision changes. Offering it invites a misreading. |
| **The 2.2×-below-chance proximity null** | **Marginal.** It is a mild argument against GEO proximity-risk inflation, which cuts *against* selling anything. | Cited in a market commentary at most. | The null construction is close to tautological (§2). |

---

## 4. The measurement-genre pieces, judged individually

- **"First public recall figure for a TLE manoeuvre detector" — the premise is false.**
  Four independent published recall measurements against mission-published manoeuvre
  histories exist, three of them on these very spacecraft, and one group has released a
  15-satellite ground-truth benchmark with threshold-swept precision–recall curves (§2,
  first row). What this programme has is its **own** first recall, which is a real and
  necessary internal milestone and nothing more. Worse, the *number* is an outlier on the
  low side: 7.94% against published 0.35–1.00 on overlapping spacecraft. The genuine
  finding buried inside it is an engineering one — the shipped threshold is set from a
  population-median noise term 130–470× coarser than the objects under test, so the
  detector is mis-calibrated for any well-tracked satellite, and correcting that is cheap
  and already measured (11.29%). Fix it before quoting the recall anywhere outside the
  repository. The 86%-below-floor split is still the sharpest statement of the sensitivity
  limit, but it sits beside an already-published fact: the labelling dataset itself reports
  a ~24 m element-set noise floor against a median real response of 20.3 m.
- **Constant covariance columns.** Strongest cost-to-value ratio in the programme:
  falsifiable in an afternoon, consequential for a real safety chain, independently
  replicated, and sitting in a gap that the responsible institutions have described in
  print and not filled. Needs hardening, not more cleverness.
- **The parameter-free burn-direction result.** Beautiful, textbook-grounded, post hoc.
  Its value is as a validity check on the whole harmonic line, not as a detector
  improvement — the programme is right that knowing the sign buys +1.9 dB of response and
  no separation at all. Replicate it under registration and publish it as a short note.
- **The audited alarm that publishes its own fired gate.** The genuinely novel practice;
  two independent sweeps found pre-registration and published false-alarm auditing
  essentially absent from this field. But a practice is adopted only when shown to *change
  an answer* — here it did, twice (32.8% → 0.103%; the low-orbit arm withdrawn after failing
  its own control). Those two case studies, not the apparatus description, are the paper.
- **The tandem catalogue with 93.9% proven keeping.** A real dataset with a real
  positive-evidence criterion. Its weakness is that it proves *control*, not
  *coordination*; the phase-lock statistic is the only coordination evidence and it is a
  1.59× ratio on a 44.1%-vs-27.7% comparison. State it that way.
- **The 2.2×-below-chance null.** The weakest of the six. Keep it, scope it hard, never
  lead with it.

---

## 5. The operator's self-consistency idea — assessed

**The idea:** measure a megaconstellation operator's own prediction error by comparing an
earlier published ephemeris against their later, better-informed one.

**Verdict: the self-consistency measurement alone is already occupied, and would not be a
paper.** Opened: arXiv:2510.11242 does exactly this — "each three-day ephemeris was
compared to overlapping segments from newer forecasts" over ~1,500 satellites and two
months, reporting ~300 m position RMSE for stable satellites and ~600 m for deorbiting
ones. arXiv:2605.19850 (opened) runs the sibling experiment with next-element-set-as-truth
across 24,641 pairs. An open archive project (`Kira-Ryan/ephemera`, opened, started
Aug 2026) is collecting the files daily and names the metric "self-consistency,
contaminated by re-plans" in those words.

**But the pairing is not occupied, and it is the note worth writing.** Take the measured
self-consistency residual at each lead time and test it against the **published
covariance at that same lead** — the standard containment test, Mahalanobis distance
against a chi-square expectation, exactly as Park et al. (LeoLabs, AMOS 2019, opened) did
for their own data (95.2% of distances ≤ 4.0; realism held through 7 days). Nobody
located has run that test on the public megaconstellation files. Combine it with the
constant-column census and the note writes itself in about four pages:

> at short lead the published uncertainty is a formal filter output of sub-metre scale
> that no independent measurement has honoured; at 24 h and 72 h it is not an uncertainty
> at all but a small set of fixed values; and here is the containment curve.

**Would insurers and operators care?** Operators **yes** — they screen against these
files. Regulators and space-traffic-management policy **yes**. Insurers **weakly**, as a
governance fact rather than a rating fact (§3). Do not oversell it as a market story.

**Four honesty conditions, all mandatory.** (1) A later prediction is not truth; the word
throughout must be *self-consistency*, never *accuracy* — the provider realism study cited
above has the same limitation, and an independent truth source is the stronger design.
(2) Re-plans contaminate the residual: declared manoeuvre epochs must be excluded and the
excluded fraction reported. (3) The constant-column claim must be re-measured over months,
not one 250-file sample — though it now has independent support (§2). (4) If an independent
truth source is used, it must not be geodetic spheres alone: a 2025 argument holds that
validating against low-area-to-mass spheres gives "overly optimistic assessments".

One supporting check is already done: the operator's public ephemeris README (opened)
states only that the files carry "position and velocity covariance" over 72 hours updated
every 8 hours, and defers all format detail to a handbook behind a login. **No public
documentation of how that covariance is generated, or of any default or cap, was located.**
The fair statement is: published, publicly undocumented, and constant over most of its span.

---

## 6. Threads to pull — ranked

| # | Thread | The measurement that makes it a paper | Audience |
|---|---|---|---|
| 1 | **Covariance realism of public megaconstellation ephemerides** | Mahalanobis containment of overlap residuals against the published covariance, by lead time, over a multi-month archive of every file, declared-manoeuvre epochs excluded and counted; plus a distinct-value census per lead column. | Conjunction assessment / SSA practitioners; regulators and space-traffic-management policy; secondarily reinsurance emerging risk. |
| 2 | **A cross-method recall comparison on one common benchmark** — reframed after the survey. The gap is *not* that recall is unpublished; it is that, in the benchmark authors' own words, existing contributions "evaluate their algorithms on different satellites, making comparison between these methods difficult". | First recalibrate the shipped detector to per-object noise (measured: 7.94% → 11.29%, labelled-quiet count unchanged) so it is not an outlier for the wrong reason. Then run three or more published detector families **at matched false-flag rate** over the released 15-satellite benchmark *and* the 1,134-event label set, and publish recall by burn-size decile with each detector's derived sensitivity floor beside it. | SSA / astrodynamics. The comparison paper the field says it lacks, and the only framing in which this programme's own number becomes a contribution rather than a liability. |
| 3 | **The GEO control problem, named and then solved** | Build a passive control on *epochs of free libration inside a history* rather than on whole objects, validate it against synthetic librators and synthetic keepers, and report the leak rate of the approach detector against it. | SSA methods. This is the blocker on every GEO claim in the programme; solving it unlocks T8a, T11 and the alarm simultaneously. |
| 4 | **Slot-side burn direction, under registration** | Pre-register the sign function on an independent object set; report the coverage problem (47% of carriers have no readable phase) as a primary result, not a caveat. | Astrodynamics — a short, clean note. |
| 5 | **The tandem-pair catalogue as a public dataset** | Publish the 239 pairs with arrival order, dwell and the phase-lock statistic, with the "geometry plus positive control evidence, not proven coordination" scope on its face. | GEO operators, slot coordination, SSA; possibly servicing underwriters. |
| 6 | **An externally-observed propellant bound — the highest-value target in the programme, and currently out of reach** | Not a paper yet. The prerequisite is recall: lift the detector off its population-median threshold, measure recall on station-keeping-sized burns specifically, and build an onset detector for electric propulsion, which the programme concedes it does not have above the drag regime. Only then does a bound with a stated error become publishable — and the error it must beat is on the order of a year of life. | Satellite finance, life-extension and residual-value cover. Verified open lane: no published method estimates remaining propellant from purely external observation. |
| 7 | **Pre-registration as a case study, not as an apparatus** | Two worked cases where a registered check changed the answer — the 32.8% → 0.103% denominator correction and the LEO arm withdrawn after failing its own passive control — written for a methods audience. | Astrodynamics methodology; this is the programme's most transferable output. |

---

## 7. Threads to drop

1. **The matched-filter / template-bank detector programme (T5a).** Two template families
   falsified on the same 208 objects, the one statistic that gains is not a matched filter,
   no injection-recovery or recall arm exists anywhere in the track, and the compute ask is
   already withdrawn. Keep the whole-history stacking result and the registered
   confirmatory; drop the template line and do not propose a third family.
2. **The behavioural alarm as a public product or site surface.** Measured precision
   0.103% overall and 3.41% at best; tightening the dial does not improve it; the LEO arm
   failed its own passive control and was correctly withheld; GEO has no leak-free control
   at all; and the one lever the programme's own certainty doctrine ranks first —
   conditioning the routine-operations null on public slot filings — came back
   **feasibility WEAK**, with roughly a third of ordinary GEO operations off-filing
   anyway. That combination means the precision problem has no cheap fix. Keep the alarm
   as a measured artefact; do not ship it to readers.
3. **The fuel odometer as an underwriting or valuation input.** At 1.81% of the
   north–south budget detected and an empty electric arm, the bound is directionally safe
   and informationally empty. Withdraw the underwriting framing from Paper A's §1.4 until
   recall moves an order of magnitude; keep the "free, public and audited" framing, which
   is defensible.
4. **The cadence-fingerprint line as a novelty claim.** 7- and 14-day east-west cycles are
   standard practice; the registered per-object test was null; the window threshold has
   failed to transfer three times with the control firing *above* the treated class. Keep
   it as instrument validation and as the input to the deadband derivation — which is
   where it has earned its place — and stop presenting it as a finding.
5. **Any priority claim attached to the recall measurement, and any framing of the cadence
   or taxonomy work as new.** Both territories are occupied in print (§2). Keep the work,
   drop the claim — and update the runbook and Paper B so the correction travels with the
   number rather than being discovered by a referee.
6. **The filed-slot null (T15).** Already parked; the feasibility sweep is correct that no
   public source keys catalogue numbers to filings and that ~20% non-compliance plus ~15%
   unfiled arcs destroy the label. Leave it parked and stop describing it as the largest
   precision lever, because a lever that cannot be built is not a lever.

---

## 8. Cross-cutting things that would not survive an expert referee

- **"Reported, not claimed" is doing very heavy lifting.** T10a, T10b, T10c and T3's line
  profiles all end there. A referee counting publishable effect sizes finds few.
- **Detector properties masquerading as behaviour.** The programme catches this itself
  three times (the taxonomy's skill collapsing to +0.001 on flagged events; gate H in LEO;
  the 14.00 d control firing above treatment). It should be stated once, prominently, as a
  standing limitation rather than rediscovered per track.
- **Registration defects are now frequent enough to be a finding in their own right** — a
  contradicted bar, a tolerance fixed without the precision it would be compared against, a
  prior chosen against an imagined base rate, a control that could not have discriminated,
  a surrogate that measured the envelope. The honest write-up of *how registrations fail*
  would be a more original contribution than several of the tracks.
- **The prior-art discipline is good and its coverage is uneven.** The proximity sweep is
  exemplary. The manoeuvre-detection territory is not: four published recall measurements
  against operator truth, a released 15-satellite ground-truth benchmark, a population-scale
  cadence study over 1,707 geostationary objects and a 918-satellite behavioural clustering
  were all missed, and several of them sit in the same conference proceedings the programme
  already cites. Before any further "not located" claim is made, the two European space-debris
  conference proceedings and the optical-surveillance conference library should be swept
  systematically rather than by keyword.
- **Nothing in this programme has ground truth at GEO.** Every GEO number is agreement
  between rule sets on one archive. The LEO truth set is eleven spacecraft. Say it at the
  top of every GEO document, not in section 9.

---

## 9. What was opened, and what was not

**Opened and read:** arXiv:2510.11242 (megaconstellation ephemeris data quality;
overlapping-segment self-consistency); arXiv:2605.19850 (SGP4 vs high-fidelity against
operator-updated truth, 24,641 pairs); Park et al., "Statistical Covariance Realism
Assessment of LeoLabs' Orbit Determination System", AMOS 2019 (full text extracted); the
`Kira-Ryan/ephemera` project page; the operator's public ephemeris README; the programme's
own runbook, both paper drafts and the results documents named in §2.

**Opened in full text by parallel surveys and relied on here.** For §2 and the cadence row:
Kelecy, Hall, Hamada & Stocker, AMOS 2007; Decoto & Loerch, AMOS 2015;
Cipollone, Raviola & Di Lizia, ESA SDC9 2025 (paper 249); Shorten, Yang, Maclean &
Roughan, arXiv:2212.08662 / JSR 10.2514/1.A35642, and the companion arXiv:2312.02460 /
Acta Astronautica 228:709 (2025); Pastor et al., ESA SDC8 2021 (paper 233); Roberts &
Linares, AMOS 2021; Roberts et al., AMOS 2023; Siew et al., AMOS 2023; MAD-LEO
(arXiv:2609.08556). For element-set accuracy context: Flohrer et al., ESA SDC5 2009 and
AMOS 2008; Vallado, Bastida Virgili & Flohrer, ESA SDC6 2013; Levit & Marshall, Adv. Space
Res. 47(7) 2011; Oltrogge & Ramrath, AMOS 2014; Kelso, AAS 07-127; Kelso & Kuciapinski,
IAC-25-A6.7.1; Acciarini, Baydin & Izzo, Acta Astronautica 226 (2025). For covariance and
standards: NASA
*Conjunction Assessment and Collision Avoidance Best Practices Handbook*, SP-20230002470
Rev 1 (2023); Ramos et al., AMOS 2023; *Spaceflight Safety Handbook for Satellite
Operators* v1.7 (2023); the 2024 civil traffic-coordination orbit-data-format
recommendation; Zaidi & Hejduk, AIAA 2016-5628; Hejduk, Snow & Newman (dilution region,
2019); Cano, Pastor & Escobar, ESA SDC8; Bastida Virgili et al., IOC 2019; Bhattarai et
al., AMOS 2025; Olson et al., AMOS 2024. For §3: Undseth, Jolly & Olivari, ESA SDC8 2021;
Kunstadter, ESA 2021 and IAC-22 (with McKnight et al.); Aon, *Space Insurance Market
Report* Q1 2026; Swiss Re, *Space debris: on collision course for insurers?*; Mandyam,
McKnight & Dale, IOC 2023; Analysys Mason, *The business case for satellite life
extension* (2016); two Lloyd's innovation case studies; World Economic Forum, *Clear Orbit,
Secure Future* (2026).

**Unverified — snippet or abstract only:** Lemmens & Krag, JGCD 2014 (10.2514/1.61300),
**the one gap that matters and it is paywalled**; Patera, JSR 45(3) 2008; Remote Sensing
2025 (10.3390/rs17172994); Fu (arXiv:2605.09790); Poore et al., uncertainty-realism working
group (2016); Rao & Szumilo 2026 (geostationary relocation behaviour); Pessina et al.,
ISSFD 2015; the classical triaxiality literature and Soop's geostationary handbook; the
journal series on operator-released megaconstellation ephemerides (403 on fetch);
external-observation propellant-gauging patents and theses; trade-press coverage of the
2025–26 insurance market, **including the deductible-waiver claim, which must not be cited
until confirmed with the carriers named**.

**Could not be reached:** many publisher platforms returned 403; commercial provider
methodology is marketing-level only; restricted and paywalled defence literature is outside
this survey by construction. One caution to carry: two convenient megaconstellation sources
— a single-author unreviewed preprint and an open archive project — read as coming from the
same independent quarter as this programme, and should be checked for independence before
either is cited as arm's-length prior art.
