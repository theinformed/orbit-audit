# T8b results: LEO, MEO and HEO approach events from plane matching and phasing

Measured 2026-09-22. Registration: `docs/proximity-leo-preregistration-20260922.md`,
committed **alone** at `23d4776` before any measurement code existed; the
instrument and its 74 tests followed at `07fc2d5`. The ordering in `git log` is
the evidence. Every threshold below was fixed in that registration and none was
changed after a number existed.

Framing, restated because it constrains this document: the instrument is
**ownership-agnostic mathematics**. Catalogue registry codes are metadata
columns on the event rows and enter no detector decision; this document
contains no intent language and no per-nation narrative, and the one
registry-related figure reported (§3.4) is stated as arithmetic without
interpretation, because that framing is an operator decision reserved to Sean.
The object whose elements changed is the approacher — **facts, never intent**.
Plane changes are reported in degrees and orbit changes in kilometres; **no
velocity, propellant or consumables figure was computed for any object**, and a
test asserts that no event row carries one.

**Read §1.1 before any number in this document. No figure here is a miss
distance.** T8b's estimand is a *co-orbital station*: matched plane, matched
altitude, bounded relative phase, sustained. §2.7 of the registration derives
why a miss distance is not obtainable from public two-line elements at all.

---

## 0. The nine registered gates, discharged

| Gate | Registered meaning | LEO | MEO | HEO |
|---|---|---|---|---|
| **A** | **the instrument is unfit** | **FIRED** | **FIRED** | **FIRED** |
| **B** | the geometry arm leaks | not fired (**0.000** vs a bar of 0.10) — but see §7.2: it **fires at θ_p = 1.0°** | not fired | not fired |
| **B′** | the corroboration is decorative | not fired | **FIRED** | **FIRED** |
| **C** | the null explains the catalogue | not fired — the observation is **18× ABOVE** the null | not fired | not fired |
| **D** | underpowered | not fired (71 ≥ 20) | **FIRED** (2) | **FIRED** (0) |
| **E** | no lead time | not fired | not fired | **undefined** (no event) |
| **F** | the lead time is censored by its own window | not fired (1.4%) | not fired | undefined |
| **G** | the dwell bound is unvalidated | not fired — but at **exactly 5.0%** against a bar of 5% | **FIRED** (8.5%) | **FIRED** (20%, n = 5) |
| **H** | **the manoeuvre detector cannot corroborate** | **FIRED** under every reading | **FIRED** | **FIRED** |

**The one-paragraph verdict.** The mathematics works and the control works: the
manoeuvre-history control T8a said had to be constructed returns **exactly zero
events across 18.79 million object-days**, where T8a's inherited `object_type`
control leaked at parity. The lead time is real, long, and 5.4 times GEO's:
**median 196 days** of causal warning in LEO, at **44.1% precision**, against a
stratum-matched null the observation beats by a factor of 18 with zero of 1,000
permutations reaching it. But **two registered gates fired and they are the same
defect seen twice**: the registered plane-noise calibration (§2.2) came back 145
times too large, which set the plane-manoeuvre threshold to 3.5° and switched
off the plane channel almost entirely — so **the plane-matching campaign the
registration was built to detect is essentially never observed, and what T8b
actually catalogues is in-track phasing campaigns inside an already-shared
plane.** The lead time is a lead time for *that* class, and this document says
so everywhere it quotes it.

---

## 1. What ran, where, and for how long

| | |
|---|---|
| Host | `pc` (`bigmem-PC`), CPU only, `nice`-d <!-- src: docs/proximity-leo-20260922-receipt.json, host --> |
| GPU | **measured and rejected** — see §1.2. The GPU was exercised through the broker; it lost by 12.8×. |
| Extract pass | **757.4 s**; **217,026,192** element sets scanned over **68,749** objects, all cached |
| Detect pass | **322.5 s** (calibration + the manoeuvre detector over every object) |
| LEO analyze | **629.8 s**;  LEO nulls **412.5 s**; nine LEO threshold arms, MEO and HEO |
| Archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, 13,891,362,816 bytes, 3,391,446 pages, read-only with `PRAGMA query_only=1` |
| Archive span | `month_rollup` 1959-01 … 2026-09 |
| Outputs | `docs/proximity-leo-events-20260922.jsonl` (LEO primary, sha256 `39321a4b…4611b`), `docs/proximity-leo-meo-events-20260922.jsonl`, `docs/proximity-leo-heo-events-20260922.jsonl`, `docs/proximity-leo-20260922-receipt.json` |

**The provenance discrepancy T8a found is still there and is larger.** The
sequential pass counted **217,026,192** element sets; `month_rollup` reports
**183,371,676**. The rollup understates the archive by **33,654,516 rows**
(15.5%). T8b, like T8a, takes the scan as ground truth. Any study that sizes
this archive from `month_rollup` is reading a number that is 15% low.

### 1.1 What the estimand is, and is not

An event is a **co-orbital station**: the two objects' orbit *planes* agree to
θ_p, their relative along-track *phase* stays inside ±Γ, and both hold for at
least D days. At the primary arm (θ_p = 0.2°, Γ = 5°, D = 30 d) and at a 500 km
LEO altitude that is a box roughly **24 km across-track, 600 km along-track and
— by the registration's §2.5 phase-confinement bound — 0.14 km in altitude**.

It is **not** a close approach and **not** a miss distance. The registration
derives why (§2.7): two near-circular orbits of similar radius *always* cross,
whatever their plane separation, so a miss distance is decided entirely by a
5,479 deg/day fast angle — at a positional accuracy public elements do not
carry. **This is a registered change of scope against the programme runbook**,
which recorded "T8b owns miss distance". T8b does not, and no amount of compute
changes that: a conjunction instrument needs special-perturbations ephemerides,
which is track T6.

### 1.2 CPU versus GPU, measured rather than assumed (registration §8.2)

The registered sub-problem — the 200 screening epochs beginning at the median
epoch of the LEO regime, all objects present — was run on both paths, returning
the **identical 66,552 pairs**:

| Path | Wall clock | Pairs | Peak device pool |
|---|---:|---:|---:|
| CPU (NumPy, `nice`-d) | **0.534 s** | 66,552 | — |
| GPU (CuPy via `/home/sdegan/gpu-broker/gpu-run --estimate-mib 900 --class standard`, beside resident training) | 6.823 s | 66,552 | 197,120 B (0.0001× the registered 2 GiB cap) |

**The CPU wins by 12.8×, and the reason is physics rather than engineering.**
The registration's §2.5 phase-confinement bound makes the semi-major-axis
screening window 0.237 km wide, which collapses each screening epoch from an
O(N²) problem over ~20,000 objects to a sparse neighbour list of a few hundred
pairs. At that size the per-epoch kernel launches and host synchronisations
dominate, and 1,644 of them cost more than the arithmetic saves. **The derived
bound made the problem small enough that a GPU loses.** The full screen ran on
CPU in 129.1 s. The GPU path is retained, tested and reported; it is not used.

---

## 2. Population and calibration

### 2.1 The regime census

One sequential pass, binned per element set by the registration's §3.1 rule:

| Regime | Element sets | Objects | Object-days |
|---|---:|---:|---:|
| **LEO** | 177,780,726 | 61,861 | 112,828,396 |
| **MEO** | 4,288,937 | 1,084 | 3,332,027 |
| **HEO** | 23,307,057 | 8,532 | 17,150,632 |
| near-GEO (T8a's band, excluded) | 11,627,368 | **1,768** | 7,674,219 |
| perigee below 100 km | 22,104 | 1,052 | 9,308 |

The near-GEO count of 1,768 reproduces T8a's population exactly, which is the
check that the two catalogues partition the archive without overlapping.

The daily grid the analysis runs on holds **61,734 LEO objects over 112,826,797
object-days**. The 127-object and 1,599-object-day shortfall against the census
is reported rather than smoothed: the grid keeps the *first element set of each
UTC day*, so an object whose LEO rows are never the first row of their day (it
was in another regime earlier that day) is absent. It is 0.2% of objects and
0.001% of object-days.

### 2.2 The two calibrated quantities, and gate A

| Quantity | Registered definition | Measured (median) | Measured (p95) |
|---|---|---:|---:|
| `σ_θ` | MAD of the second difference of the angle between consecutive orbit normals, per object, pooled by object | **0.6994°** | **2.9026°** |
| `σ_n` | MAD of the second difference of mean motion, same pooling | 6.2747e-5 rev/day | 5.3954e-3 rev/day |

**Gate A fires on both clauses**, and the registration's §10.0 rule — each bar
is a formula *and* its evaluated number, so the two cannot disagree — leaves
nothing to arbitrate:

| Clause | Bar (formula) | Bar (number) | Measured | Verdict |
|---|---|---:|---:|---|
| plane noise | `σ_θ(p95) ≤ θ_p/10` | 0.02° | **2.9026°** | **FIRES, by 145×** |
| altitude noise | `σ_n → |δa| ≤ (Γ/(k D))/10` | 0.01583 km | **0.02145 km** | **FIRES, by 1.36×** |

> **Gate A: the instrument is unfit.** Stated in the registered words, for all
> three regimes.

### 2.3 Why σ_θ came back 145× too large, and what it cost

The registration asserted that the second difference of the inter-normal angle
"annihilates any smooth secular rotation and leaves fit-to-fit scatter". **It
does not.** The angle between consecutive orbit normals is the J₂ nodal
rotation *times the epoch spacing*, and the archive's spacing is irregular
(LEO median 0.53 d, p95 2.35 d). Second-differencing that sequence measures the
irregularity of the sampling far more than it measures the fit. At a 500 km,
53° orbit the nodal rate is 4.6 deg/day, so a spacing that wobbles by half a
day moves the statistic by degrees — which is exactly the 0.70° that came back.

**This is not cosmetic. It disabled half of the registered signature.** The
plane-manoeuvre threshold of §5.4 is `max(5σ_θ, 0.01°)`, i.e. **3.5°** — larger
than almost any real plane manoeuvre. The consequence is visible in every
worked example in §8: **`planeManoeuvresInCampaign` is zero for every arm-M
event in the LEO catalogue.** Only 1,174 of 18,865 payload-class objects carry
a detected plane manoeuvre anywhere in their history. The plane-matching
campaign — the thing the registration's physics was built around — is
essentially **not observed**, and §3 explains what the catalogue contains
instead.

### 2.4 The quantity gate A should have named (a diagnostic, not a threshold)

Added at measurement time and labelled as such, in the manner of T8a's §2.4.
The registration did not register a *direct* plane-direction noise floor, so
one is measured here: the residual of `i` and `Ω` from a centred five-point
median of each — which annihilates any smooth motion, regular or not, and
leaves only fit-to-fit scatter — converted to a plane angle by §2.1. 673 LEO
objects sampled at stride 60:

| | p5 | p25 | **median** | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| plane-direction scatter (°) | 0.0 | 0.0 | **0.000148** | 0.000297 | 0.000741 |
| …as cross-track km at a = 7234.5 km | — | — | **0.0187** | 0.0375 | 0.0936 |
| mean-motion scatter as δa (km) | 0.0 | 0.0 | 0.0 | 0.0054 | 0.0188 |

**On the quantity that actually decides an event, the instrument is 135× inside
gate A's bar at the median and 27× inside it at the p95.** The registered
statistic and the decisive statistic disagree by more than three orders of
magnitude, and the registered one is the one that governs the verdict in §0.

The δa diagnostic is the less comfortable half: its p95 of 18.8 m sits *above*
gate A's 15.8 m bar, so the altitude clause of gate A is marginal rather than
spurious. At the primary Γ = 5° the phase-confinement bound is 158 m, so the
primary arm has 8× of headroom; the tightest registered arm (Γ = 0.2085°,
25 km) implies a 6.6 m tolerance and **is below the noise**. §5 reports that arm
and labels it.

### 2.5 The classes, and the size of T8a's contamination

The registration's §3.4 control is manoeuvre history, not `object_type`.
Measured over every object's whole archive history:

| Population | Count |
|---|---:|
| **`never_manoeuvred`** (zero detected manoeuvres, ≥ 200 element sets, ≥ 365 d span) — **the control** | **3,011** |
| excluded from the control for thin evidence | 11,150 |
| `catalogue_passive` (`object_type` ∈ DEBRIS, ROCKET BODY) — T8a's failed control | 12,640 |
| `payload` | 18,865 |
| …of which carry a detected **plane** manoeuvre | 1,174 |
| **`payload` AND `never_manoeuvred`** — the dead payloads T8a's control could not see | **855** |
| `catalogue_passive` NOT `never_manoeuvred` | 10,863 |
| `catalogue_passive` AND `never_manoeuvred` | 1,777 |

**855 payload-class objects have never manoeuvred in their whole recorded
history.** That is the population T8a's §7.3 identified as the cause of its
control failure, counted directly. And the mirror figure — 10,863
catalogue-passive objects that *did* trip the detector — is §7.3's problem
rather than a finding about rocket bodies: at 87.4% of the class it is the
in-track channel firing on drag (§7.3, gate H).

---

## 3. The LEO event catalogue

### 3.1 Primary arm: θ_p = 0.2°, Γ = 5°, D = 30 d

| | count |
|---|---:|
| Screening epochs (15-day grid) / object-epochs | 1,644 / 8,922,834 |
| Candidate pairs after the provably admissive screen | **176,257** |
| Raw geometric dwells satisfying criteria 1 and 2 | **2,565** |
| …attributed **`natural`** (the closure was J₂'s) | **1,127** |
| …attributed `ambiguous` (both objects moved comparably) | 1,075 |
| …attributed `target` (the other object moved; role swapped) | 481 |
| …attributed `approacher` | 124 |
| **Arm G** (geometry: criteria 1, 2, 3a, 3b) | **120** |
| **Arm M** (arm G + manoeuvre corroboration) — **the registered catalogue** | **71** |
| Standing co-orbital pairs (never separated; **not** events) | **6,322** |
| Distinct arm-M approachers / targets | **55 / 58** |
| Distinct arm-M arrivals | 68 |

**Rejections, counted rather than dropped in silence**: 332,201 candidate
dwells too short; 189 broken by a gap > 5 d; 1 failing the occupancy bar;
3,984 with no usable look-back.

**44% of geometric dwells are J₂'s doing.** That is the registration's §2.4
false-alarm mechanism, measured: for any pair whose inclinations differ by less
than θ_p, co-planarity is not merely probable but certain, twice per relative
nodal cycle, with no manoeuvre at all. The counterfactual of §4.5(a) — each
object propagated forward from t₀ at its **own** J₂-predicted nodal rate — is
what separates them, and it removes 1,127 dwells that a geometry-only detector
would have called events.

### 3.2 Distributions (71 arm-M events)

| Quantity | p5 | p25 | **median** | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| Dwell duration (d) | 31.0 | 41.3 | **55.3** | 76.7 | 240.2 |
| Closest plane separation (°) | 0.0 | 0.00057 | **0.01625** | 0.03907 | 0.05980 |
| …as cross-track km at a = 7234.5 km | 0.0 | 0.07 | **2.05** | 4.93 | 7.55 |
| Median plane separation during the dwell (°) | 0.0 | 0.00354 | **0.01958** | 0.04398 | 0.07328 |
| Closest along-track angle \|γ\| (°) | 0.0 | 0.01796 | **0.2069** | 1.0834 | 2.8870 |
| …as along-track km | 0.0 | 2.3 | **26.1** | 136.8 | 364.4 |
| Median \|γ\| during the dwell (°) | 0.0 | 0.657 | **2.381** | 3.751 | 3.964 |
| Median \|δa\| (km) | 0.0 | 0.0029 | **0.0065** | 0.0141 | 0.1742 |
| Campaign duration (d) | 5.9 | 29.3 | **70.6** | 210.3 | 587.0 |
| Plane closure `C` (°) | 0.00087 | 0.01404 | **0.03567** | 0.08221 | 0.14095 |
| Apsidal separation \|Δω\| (°) | 0.0 | 2.30 | **7.84** | 19.15 | 33.04 |

**The plane-closure column is the finding.** The registered thresholds treat a
plane closure of 5° or more as the campaign (θ_far = 5°), yet the median
registered event closes **0.0357°** — a seventieth of a degree. The events in
this catalogue did not match planes; **they were already co-planar and they
closed the along-track phase.** Median \|δa\| of **6.5 metres** says the same
thing from the other side: these are actively phase-locked pairs.

### 3.3 What the catalogue actually contains

Stated plainly, because the registration's title promises something else. The
LEO arm-M catalogue is dominated by **in-track phasing campaigns between
objects that already share a plane** — overwhelmingly, members of the same
large constellation manoeuvring relative to one another. Three facts carry it:

1. plane closure median 0.0357° against a 5° prior-separation bar (§3.2);
2. `planeManoeuvresInCampaign` is **zero for every one of the 71 arm-M events**;
3. the approacher list (§8) is 55 objects of which the majority are members of
   two large LEO constellations.

Whether that is the *whole* truth about LEO approach behaviour cannot be
answered from this catalogue, because §2.3's calibration defect made the plane
channel blind. **What can be said is that at the registered scope, with the
plane channel switched off by a bad noise floor, LEO approach events are
phasing events.**

### 3.4 One structural metadata split, reported without interpretation

**69 of the 71 arm-M events (97.2%) carry the same catalogue registry code on
approacher and target.** The figure is arithmetic on a metadata column that no
detector branch reads; T8b draws no inference from it and offers no per-nation
narrative. It is reported because omitting it would be a choice too.

### 3.5 Sensitivity arms (LEO, all run in full)

| Arm | θ_p | Γ | D | Pairs | Raw | Arm G | Arm M | `natural` | Standing | KM median lead (d) | Never-manoeuvred control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| | 0.05° | 5° | 30 | 99,239 | 1,957 | 97 | 31 | 703 | 5,494 | 219.0 | **0** |
| | 0.1° | 5° | 30 | 133,303 | 2,252 | 111 | 54 | 886 | 6,011 | 220.8 | **0** |
| **primary** | **0.2°** | **5°** | **30** | **176,257** | **2,565** | **120** | **71** | **1,127** | **6,322** | **195.9** | **0** |
| | 0.5° | 5° | 30 | 243,561 | 3,278 | 141 | 85 | 1,669 | 6,775 | 171.6 | **4** |
| | 1.0° | 5° | 30 | 292,915 | 4,013 | 166 | 104 | 2,310 | 7,063 | 219.0 | **6** |
| | 0.2° | 1.0° | 30 | 132,585 | 632 | 60 | 24 | 246 | 748 | **17.5** | 0 |
| | 0.2° | 0.2085° (25 km) | 30 | 67,532 | 522 | 65 | 27 | 188 | 325 | **4.4** | 0 |
| | 0.2° | 5° | 14 | 251,048 | 6,890 | 304 | 170 | 3,269 | 22,323 | 196.9 | 0 |
| | 0.2° | 5° | 60 | 115,279 | 1,049 | 46 | 25 | 479 | 1,535 | 196.9 | 0 |

Two things move across this table and both are derived rather than surprising.

**The control leak switches on with the plane threshold, exactly where the
physics says it should.** The never-manoeuvred class returns **zero** events at
θ_p ≤ 0.2° and starts returning them at 0.5°. §7.2 gives the ratios.

**The lead time belongs to the loose phase band.** It is stable at 196–221 days
for Γ = 5° and for every D, and it **collapses to 17.5 days at Γ = 1° and 4.4
days at Γ = 0.2085°**. A tightly phase-locked station is reached by an arresting
burn immediately before arrival, so the initiating manoeuvre of the campaign is
that burn; a loosely confined one is the end of a long chain. Both numbers are
true of different event classes and neither generalises to the other.

---

## 4. Lead time — the headline number

For each arm-M event the registered `lead_causal` runs from the **confirmation**
of the campaign's **initiating** manoeuvre (the second consecutive element set
showing it — the first instant a causal observer possessed the evidence) to the
arrival. The registration made the **Kaplan–Meier survival curve primary** and
percentiles secondary, specifically to discharge the one blind spot T8a failed
to declare.

**71 of 71 arm-M events (100%) had an initiating manoeuvre inside the 1,095-day
look-back.** Nothing is censored for absence.

| | p5 | p25 | **median** | p75 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| `lead_causal` (d), n = 71 | 8.74 | 70.5 | **195.9** | 473.9 | 917.5 | 1,080.9 |
| Kaplan–Meier | — | 70.1 | **195.9** | 496.1 | — | — |

**Censoring, stated plainly.** 1 of 71 events (1.4%) sits at or beyond the
1,050-day wall, against gate F's 20% bar. **The registered 1,095-day look-back
is long enough**, which is the direct repair of T8a's undeclared blind spot: its
180-day window truncated a distribution whose LEO median is 196 days and whose
p95 is 918 days. A 180-day look-back would have missed the initiating manoeuvre
of **53.5% of these events (38 of 71).**

### 4.1 Against GEO

| | T8a (GEO) | **T8b (LEO)** | ratio |
|---|---:|---:|---:|
| median causal lead (d) | 36.1 | **195.9** | **5.4×** |
| fraction with a confirmable initiating manoeuvre | 66.9% | **100%** | — |
| alert precision | 32.8% [30.5, 35.3] | **44.1% [36.7, 51.8]** | — |

The registration derived the *direction* of this result before it was measured
and did not derive the size: 100 km of altitude buys 0.234 deg/day of relative
nodal drift for 55 m/s, against 133 m/s for a single degree bought directly, so
the cheap route to a LEO plane change is months of waiting. **The measured 5.4×
is consistent with a slow campaign, but §3.3 forbids reading it as confirmation
of the plane-matching mechanism**, because the plane channel was blind: what was
actually measured is that LEO *phasing* campaigns are long.

### 4.2 The two-phase split

`lead_plane_match` — from the first epoch at which θ ≤ θ_p to the arrival —
has a median of **46.8 d** against the 195.9 d total, so a median event spends
about **76% of its warning window with the planes already matched and the phase
still closing**. In a catalogue whose plane closures are a fortieth of a degree
(§3.2) this is a statement about phasing, not about plane matching.

### 4.3 The unflattering half: what an alert would have cost

Registered in §5.8 precisely so it could not be omitted. A **plane-change
alert** is a campaign-initiating confirmed plane-type manoeuvre of a
payload-class LEO object. (The registration's literal alert — a plane manoeuvre
that closes θ_far − θ_p against *any* object — is an all-vs-all test, which is
the scope §3.3 declines and §11 hands to a cluster; what is counted is the
campaign-initiating manoeuvre itself, which is the observable a watching
operator actually has. The substitution is stated here rather than hidden.)

| | value | Wilson 95% |
|---|---:|---|
| LEO plane-change alerts over the whole archive | **161**, raised by 87 objects | — |
| Alerts ending in a registered arm-M event | 71 / 161 = **44.1%** | [36.7%, 51.8%] |
| Alerts ending in a distinct arrival | 68 / 161 = **42.2%** | [34.9%, 50.0%] |

**That is the honest shape of the capability: a median 196-day warning at a
roughly two-in-five hit rate**, over 161 historical alerts. It is a better hit
rate than GEO's one-in-three, on a third as many alerts, and it is computed on
an alert population the §2.3 defect made small.

---

## 5. Nulls — and the result that is the opposite of T8a's

### 5.1 The stratum-matched permutation null (registration §6.1(b))

1,000 permutations, seed 20260922. Each real arrival keeps its approacher, its
epoch and its **entire element history**; only the target is redrawn, from the
objects present at that epoch **in the same stratum** (regime × 10° inclination
band × 100 km altitude band), so the crowding, the shell structure and therefore
the natural differential-J₂ dynamics are preserved. Identical code decides the
observed and the null counts.

| | LEO | MEO | HEO |
|---|---:|---:|---:|
| Arrivals permuted | 120 | 5 | 2 |
| …with a stratum too thin to draw from (**labelled gap**, never a zero) | 8 | 0 | 2 |
| **Observed arm-G arrivals** | **120** | **5** | **2** |
| Null mean | **6.644** | 0.385 | 0.0 |
| Null 95% interval | **[2, 11]** | [0, 2] | [0, 0] |
| Permutations reaching the observation | **0 / 1,000** | 0 / 1,000 | 0 / 1,000 |

> **Real LEO co-orbital stations occur about 18 times more often than
> stratum-matched chance draws predict, and not one of a thousand permutations
> came close.**

**This is the mirror image of T8a's finding.** At GEO the observation sat
*below* the crowding null by a factor of 2.2, and T8a concluded that the
aggregate count carried no evidence of excess proximity. In LEO the aggregate
count carries a very large excess — but §3.3 names what that excess is: objects
inside a constellation deliberately holding position relative to one another.
The null models where objects *are*; it does not model operators choosing to fly
in formation, and the gap between the two is what the 18× measures.

### 5.2 The analytic J₂-chance null (registration §6.1(a))

Derived per pair from **each object's own fitted nodal rate**, never from a
nominal rate at a nominal altitude:

| | LEO | MEO | HEO |
|---|---:|---:|---:|
| Pairs considered | 176,257 | 1,118 | 252 |
| Pairs whose own rates permit a ≥ D-day chance co-planar window | **156,285** | 932 | 110 |
| Expected chance co-planar windows | **1,014.2** | 33.0 | 23.5 |
| Permanently co-planar pairs (zero relative nodal rate) | 3 | 0 | 0 |

**89% of the screened LEO pairs are capable of chance co-planarity by J₂
alone**, and about a thousand such windows are expected. The observed raw
geometric dwell count is 2,565 and the `natural` attribution removes 1,127 of
them — the same order as the derived expectation, which is the closest thing
this study has to an independent check that the counterfactual of §4.5(a) is
doing the job it was designed for.

---

## 6. The control — and the gate that fired at GEO and did not fire here

### 6.1 Gate B, in the registered words: **the geometry arm leaks.** It did not.

Compared per unit exposure in object-days, never as raw counts:

| Arm G, LEO primary | Events | Exposure (object-days) | Rate per object-day | Wilson 95% |
|---|---:|---:|---:|---|
| **`never_manoeuvred`** (the control) | **0** | **18,792,698** | **0.0** | [0, 2.04e-7] |
| `payload` | 59 | 29,087,754 | 2.028e-6 | [1.573e-6, 2.616e-6] |

**Leak ratio 0.000 against a registered bar of 0.10.** The registration
*predicted this gate would fire* — §6.2 says so in those words, on the strength
of §2.4's proof that chance co-planarity is certain — and it did not.

| | T8a (GEO) | **T8b (LEO)** |
|---|---|---|
| control definition | `object_type` ∈ DEBRIS, ROCKET BODY | **zero detected manoeuvres over the whole history** |
| control yield per unit exposure, as a fraction of the treated class | **0.9995** — parity | **0.000** |
| gate B | **FIRED** by a factor of 50 | **not fired** |

Two things did it, and the registration built both in on purpose: the control is
**manoeuvre history rather than a catalogue field**, so the 855 dead payloads
that wrecked T8a's control are inside it; and the **phase-confinement criterion**
is a requirement no uncontrolled object can meet — holding ±5° of relative phase
for 30 days needs \|δa\| below 158 m, which drag alone destroys.

### 6.2 Where the leak does appear: exactly where the physics puts it

| θ_p | Never-manoeuvred rate | Payload rate | **Leak ratio** | Gate B |
|---:|---:|---:|---:|---|
| 0.05° | 0.0 | 1.650e-6 | **0.000** | not fired |
| 0.1° | 0.0 | 1.960e-6 | **0.000** | not fired |
| **0.2° (primary)** | 0.0 | 2.028e-6 | **0.000** | not fired |
| 0.5° | 2.128e-7 | 2.235e-6 | **0.0953** | not fired, by a hair |
| 1.0° | 3.193e-7 | 2.647e-6 | **0.1206** | **FIRES** |

The leak switches on between 0.5° and 1.0°, which is what §2.4 predicts: widen
the plane window and you admit the J₂ chance-co-planarity that a narrow window
excludes. **The primary arm is on the safe side of a boundary the registration
derived before it was measured**, and a reader who prefers a wider plane
tolerance is entitled to know it costs the control.

### 6.3 The time-shuffled corroboration control (registration §6.3(b))

Registered because §4.7 warns that the never-manoeuvred yield in arm M is zero
**by construction** and therefore validates nothing. Each approacher's manoeuvre
epochs were shifted by a random offset drawn from ±1,095 d, 200 draws, seed
20260922 — preserving every object's manoeuvre rate and type mix exactly while
destroying the causal link to the closure:

| | LEO | MEO | HEO |
|---|---:|---:|---:|
| Arm-G events | 120 | 5 | 2 |
| **Really corroborated** | **71** | 2 | 0 |
| Shuffled mean | **24.1** | 0.76 | 0.0 |
| Shuffled 95% interval | **[18, 31]** | [0, 2] | [0, 0] |
| Gate B′ (corroboration is decorative) | **not fired** | **FIRED** | **FIRED** |

**In LEO the corroboration criterion carries real information**: the real
corroborated count is 2.9× the shuffled mean and sits far outside its interval.
A manoeuvre inside the campaign window is not something a random shift
reproduces. **In MEO and HEO it is decorative** — the real counts of 2 and 0 sit
inside shuffled intervals of [0, 2] and [0, 0] — and the results document is
required to say so in those words, which it does here.

---

## 7. What went wrong, measured

### 7.1 The dwell bound (gate G), and the T8a failure it was written against

T8a's second named failure was a dwell bound computed from a *nominal* quantity
— distance from the nominal stable longitude — which the data falsified 5 times
out of 5. T8b's analogue is the chance-co-planarity dwell bound of §2.4, and the
registration required it to be computed **only** from each pair's own fitted
nodal rates and **validated against held-out never-manoeuvred pairs before use**.

| | LEO | MEO | HEO |
|---|---:|---:|---:|
| Never-manoeuvred pairs tested | **220** | 47 | 5 |
| Exceeding their own-history bound | **11** | 4 | 1 |
| Fraction | **5.00%** | **8.51%** | **20%** |
| Wilson 95% | [2.81%, 8.73%] | — | — |
| Observed / bound, median | **0.206** | — | — |
| Observed / bound, p95 | 0.973 | — | — |
| Gate G (bar: > 5%) | **not fired — at exactly the bar** | **FIRED** | **FIRED** |

**The LEO verdict is the weakest possible pass and is reported as such.** It sits
at 5.00% against a bar of "> 5%", its interval straddles the bar, and the test
**can only under-report exceedances** — the observed dwell is measured on the
15-day screening grid, which is a lower bound on the true dwell. The honest
reading is that the own-history bound is *not falsified* in LEO and *is*
falsified in MEO and HEO, and that the LEO result should not be leaned on.

What can be said is that the own-history bound is a great deal better than a
nominal one: the median never-manoeuvred pair dwells at **0.21× its own bound**,
where T8a's nominal bound was exceeded by every single passive event it was
supposed to exclude.

### 7.2 Gate H FIRED: the manoeuvre detector's false-alarm rate

Measured on the catalogue-passive class (DEBRIS and ROCKET BODY) — an **upper**
bound, because some rocket bodies do perform disposal burns — over LEO objects
with ≥ 200 element sets and ≥ 365 days of span:

| | LEO |
|---|---:|
| Objects | 9,914 (237,796 object-years) |
| **Objects carrying at least one flag** | **8,664 (87.4%)** |
| In-track flags per object-year | **0.6373** |
| Plane flags per object-year | **0.00431** |
| Objects ever plane-flagged | 284 (2.86%) |
| Payload plane-campaigns per object-year (the gate H denominator) | 0.001554 |
| Passive plane-campaigns per object-year | 0.002061 |

| Reading of gate H's ratio | Value | Bar | Verdict |
|---|---:|---:|---|
| the literal implementation: all flags vs payload campaigns | **412.8** | 0.5 | **FIRES** |
| plane-channel flags only | 2.77 | 0.5 | **FIRES** |
| plane campaigns vs plane campaigns (the most favourable, like-for-like) | **1.33** | 0.5 | **FIRES** |

> **Gate H: the manoeuvre detector cannot corroborate.** Stated in the
> registered words, for all three regimes, under every reading.

**The in-track channel is the culprit and drag is the mechanism.** LEO drag is
not a smooth trend: geomagnetic activity moves the atmospheric density by
factors within days, and a robust local fit over ten element sets cannot
extrapolate through it. The registered own-drag term — `3·|ṅ_own|·Δt` — bounds
the *median* drag rate an object shows and not its variance, so a storm reads as
a manoeuvre. **This is the LEO analogue of T8a's libration problem**: the
confounder that a geometry detector must model, and this one did not.

Two things keep the LEO result standing in spite of it. The **plane** channel is
quiet (2.9% of passive objects, against 87.4% for in-track), and the
**time-shuffle control** (§6.3) shows that even with a noisy detector the
*timing* of a manoeuvre relative to the closure carries 2.9× the information a
random shift does. What gate H forbids is treating the corroboration flag as
evidence that an individual event was deliberate. It is evidence in aggregate
and not per row.

### 7.3 A third defect, found at implementation time and reported

The registered attribution rule (§4.5) opens its counterfactual window at `t_0`,
"the last epoch before `t_a` at which criterion 1 was satisfied" — and criterion
1 is satisfied by **either** a far plane **or** a far phase. In a phasing
campaign the phase is far until the final arresting burn, so `t_0` can land
*after* the plane has already closed, and the plane closure `C` measured over
`[t_0, t_a]` is then near zero. That is why §3.2's median plane closure is
0.0357° and why 1,127 dwells were attributed `natural`.

A **labelled, post-registration variant** was computed alongside — the identical
counterfactual, with the window opened at the last epoch at which the **plane
alone** was far. It changes no registered verdict and is offered in the manner
of T8a's §7.4:

| | registered | plane-only variant |
|---|---:|---:|
| Arm G | 120 | 53 |
| Arm M | 71 | **26** |
| Distinct arm-M approachers | 55 | 12 |
| KM median lead (d) | 195.9 | **248.8** |
| At or beyond the wall | 1 | 2 |

The variant is smaller and its lead time is longer, which is what a
plane-centred window should produce. Neither is the registered headline.

---

## 8. Worked examples (factual timelines only)

Five, chosen for clarity, including the classes that show the failure modes.
All figures are from the committed event catalogue. **Every separation figure is
a plane angle, a phase angle or a semi-major-axis difference — none is a miss
distance.** No purpose, intent or mission is attributed to any object.

### 8.1 NORAD 31698 TERRA SAR X → NORAD 36605 TANDEM X — the instrument's own check

| Arrival | Dwell | Closest θ | Closest \|γ\| | Median \|δa\| | Campaign | Plane closure | `lead_causal` | Manoeuvres (plane) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2012-04-29 | 80 d | 0.0000° | 0.000° | **0.9 m** | 23 d | 0.036° | **102.2 d** | 1 (0) |
| 2023-07-14 | 75 d | 0.0003° | 0.001° | **1.4 m** | 141 d | 0.122° | **511.8 d** | 8 (0) |

Two objects holding a mean semi-major-axis difference of about **one metre** for
two and a half months, at a plane separation the instrument cannot distinguish
from zero. This pair is the closest thing T8b has to ground truth: it is a
publicly documented co-flying pair, and the detector found it from elements
alone with no tuning. It also shows the catalogue's character — a campaign of 8
manoeuvres, **none of them plane-type**.

### 8.2 NORAD 45425 ONEWEB-0067 → NORAD 55163 ONEWEB-0622 — a repeat approacher

| Arrival | Dwell | Closest θ | Closest \|γ\| | Median \|δa\| | Campaign | `lead_causal` |
|---|---:|---:|---:|---:|---:|---:|
| 2023-10-31 | 82 d | 0.0562° | 2.721° | 3.1 m | 138 d | 196.9 d |
| 2024-02-02 | 41 d | 0.0589° | 0.076° | 2.4 m | 232 d | 290.6 d |
| 2024-03-21 | 37 d | 0.0606° | 0.257° | 4.2 m | 280 d | 338.5 d |

Three arrivals at the same target inside five months, each from a campaign of
29 detected manoeuvres, none plane-type. Plane separation is steady at ~0.06°
(≈7 km cross-track) throughout: **the plane was never matched, it was already
shared.** This is the modal event of the catalogue.

### 8.3 NORAD 48216 ONEWEB-0198 → NORAD 48236 ONEWEB-0197 — the long tail

One event: arrival 2024-01-11, dwell **197 d**, closest θ 0.0172°, closest
\|γ\| 1.457°, median \|δa\| 3.1 m, campaign 396 d, 88 detected manoeuvres,
**`lead_causal` 983.1 d**. This is the shape of the upper tail of §4: a campaign
that is visible in the public archive for nearly three years before arrival.
A 180-day look-back — T8a's — would have reported it as having no initiating
manoeuvre at all.

### 8.4 NORAD 53467 STARLINK-4394 → NORAD 53468 STARLINK-4400 — the detector-noise case

Arrival 2025-07-02, dwell 39 d, closest θ 0.0551°, median \|δa\| 10.8 m,
campaign 28 d, **`lead_causal` 1,043.7 d**, and **179 detected manoeuvres in the
look-back**. 179 manoeuvres in three years is roughly one a week, which is what
§7.2's gate H is about: for a continuously low-thrusting object the in-track
channel fires almost continuously, so "the campaign began 1,044 days ago" is a
statement about the detector as much as about the object. Included deliberately,
so the failure mode is visible rather than described.

### 8.5 NORAD 16609 → NORAD 17845 — the pre-constellation case, 1999

Arrival 1999-08-23, dwell 56 d, closest θ 0.0000°, closest \|γ\| 0.000°, median
\|δa\| 40.8 m, campaign 5 d, `lead_causal` 1,080.9 d — the longest in the
catalogue. Neither object carries a name, an object type or a launch date in the
catalogue's metadata, so no class could be assigned to either. It is recorded
here because the catalogue is not only recent and not only constellations, and
because an event whose approacher has no `object_type` is exactly the kind of
row a reader should treat carefully.

---

## 9. MEO and HEO

The same machinery, the same thresholds, reported separately and never pooled.

| | MEO | HEO |
|---|---:|---:|
| Objects / object-days on the grid | 1,044 / 3,331,793 | 8,404 / 17,148,197 |
| Screening pairs | 1,118 | 252 |
| Raw geometric dwells | 185 | 47 |
| Standing co-orbital pairs | 186 | 92 |
| Arm G / **arm M** | 5 / **2** | 2 / **0** |
| KM median lead (d) | 24.4 (n = 2) | — |
| Alerts / precision | 550 / **0.36%** [0.10, 1.32] | 1,900 / **0.0%** [0, 0.20] |
| Never-manoeuvred control yield | 0 | 0 |
| Gates fired | A, B′, D, G, H | A, B′, D, G, H |

> **Gate D: underpowered.** Fewer than 20 arm-M events. Every MEO and HEO
> distribution above is reported with its count and labelled UNDERPOWERED, and
> **no lead-time claim is made for either regime.**

Two things are nonetheless worth stating because they are not artefacts of the
small count. **The precision collapses**: 550 MEO and 1,900 HEO plane-change
alerts produced 2 and 0 events respectively, against LEO's 161 alerts and 71
events. And the **phase-confinement bound is far looser** in both — 3.69 km in
MEO and 1.94 km in HEO against LEO's 0.158 km — because the along-track
sensitivity to δa falls as `n/a`. A MEO pair can hold ±5° of phase with a
kilometres-wide altitude difference, so the criterion that made the LEO control
clean is much weaker there. That, and not any property of MEO operations, is the
most likely reason MEO's gates B′ and G both fired.

HEO's apsidal column, registered in §2.8 as the discount a reader applies: the
two HEO arm-G events have \|Δω\| that the catalogue records per row. With zero
arm-M events, nothing further is claimed.

---

## 10. Registered blind spots, as they actually bit

Each was declared in the registration's §9 before measurement.

1. **Sub-kilometre proximity is invisible and T8b measures no miss distance.**
   Unchanged and unquantifiable from inside. The median event's 2.05 km of
   cross-track and 26 km of closest along-track are *slot* figures.
2. **Continuous low-thrust plane changes are invisible or nearly so.** This bit
   hardest, and not in the way the registration expected: §2.3's calibration
   defect made the plane channel blind to *all* plane changes, continuous or
   impulsive. The declared blind spot and the undeclared defect compound, and
   the catalogue is a **lower bound on events, never a census**.
3. **Cadence and gaps.** 189 candidate dwells were broken by a gap > 5 d at the
   primary arm; 3,984 had no usable look-back.
4. **Motion below the floors.** The in-track floor is 50 m of semi-major axis
   and the plane floor was *in practice* 3.5° (§2.3), not the registered 0.01°.
5. **Catalogue completeness.** Untested and untestable from inside. **Absence of
   an event is not evidence of absence of an approach.**
6. **The regime edges are conventions**, and cross-regime approaches are not
   detected. 1,052 objects with perigee below 100 km were excluded and counted.
7. **HEO apsidal alignment is reported, not required.** With 0 HEO arm-M events
   the column is unused.
8. **The arm-G sample is a sample** — in the event it was not. The screen's cost
   allowed the **full population** rather than the registered 2,000-object
   stratified sample, so arm G covers every LEO object with a regime interval.
   Exposure is stated with every rate in §6. This is more exposure than
   registered, not less.
9. **Screening scope.** Active-payload approachers against the full catalogue,
   as registered. All-vs-all is §11.

---

## 11. The T5b handoff spec, measured against what actually ran

The registration's §11 registered what a cluster would add, before any result
existed. With the numbers in hand, each item now has a size:

1. **All-vs-all, including passive-on-passive.** T8b screened 176,257 LEO
   candidate pairs. The unordered all-vs-all is **1.91e9 pairs** — a factor of
   **10,800**. The screen ran in 129 s on one CPU core, so the naive extrapolation
   is ~390 core-hours, which is a cluster job and not a workstation one. This is
   the measurement that would turn §5.2's analytic J₂ null from a derivation
   into a validated one, on pairs where *neither* object can manoeuvre. **It is
   the single most valuable thing a cluster buys this track.**
2. **A finer time grid.** The screen's step is D/2 = 15 days, so the minimum
   detectable dwell is the registered 30 days. A daily grid is 15× the screening
   cost and opens dwells of days — the regime in which a short approach, as
   opposed to a sustained station, becomes visible. At the arm-M yield measured
   here (71 events at D = 30 d, 170 at D = 14 d) the short-dwell population is
   large and entirely unmeasured below 14 days.
3. **The full (θ_p, Γ, D) sweep rather than one-at-a-time arms.** T8b ran 9
   arms; the full grid at the registered levels is 5 × 3 × 3 = 45, and §3.5
   shows why it matters: the lead time moves by a factor of 44 across Γ and the
   control leak switches on across θ_p, so the interaction is not separable.
   A cluster does **not** fix TLE accuracy — the Γ = 0.2085° arm is below the
   measured noise floor (§2.4) and stays there.
4. **Per-object nulls instead of per-stratum nulls.** T8b's null borrows within
   a stratum, and 8 of 120 LEO arrivals already had a stratum too thin to draw
   from. `docs/matched-filter-design-20260922.md` §5.3 measured that borrowing
   across objects failed by 9.3× in T3. The per-object rung is `B` surrogates ×
   the registered screen.

**And one item T8b adds to the spec that the registration could not have known
to include**: a cluster-scale run must **re-derive the plane-noise floor**
(§2.4's diagnostic, not §2.2's registered statistic) before it does anything
else, because the registered statistic is dominated by sampling irregularity and
running the plane channel at `5σ_θ = 3.5°` wastes the entire campaign.

---

## 12. What this means for the rest of T8

Stated as findings, not as a plan; T8c/T8d scope is Sean's.

1. **The manoeuvre-history control works and should replace `object_type`
   everywhere in this track.** Zero events across 18.79 M object-days, against
   T8a's control leaking at parity. The 855 payload-class objects that have
   never manoeuvred are the population that broke T8a and they are inside this
   control by construction.
2. **The LEO lead time is long — median 196 days — and it is a lead time for
   phasing campaigns, not plane-matching campaigns.** Any T8c alarm lane built
   on it inherits that qualification, and inherits the 44% precision with it.
3. **A registered look-back must be long.** 1,095 days censored 1.4% of the LEO
   distribution; T8a's 180 days would have censored 53.5% of it. Gate F should be
   a standing requirement of the track, not a T8b-specific one.
4. **Corroboration is informative in aggregate and not per row** (§6.3 against
   §7.2). A T8c surface may use it to rank and must not use it to assert that an
   individual event was deliberate.
5. **A calibration statistic must be validated against the quantity it gates,
   before it is registered.** T8a's lesson was that a derivation is not a
   validation; T8b adds that **a noise estimator is not a noise floor**. §2.2's
   statistic is a perfectly reasonable-looking construction that measures the
   archive's sampling irregularity instead of its fit noise, and no amount of
   care in the downstream code could recover from it. The cheap repair — measure
   the residual from a centred local fit, which annihilates smooth motion at any
   spacing — costs one function and is in §2.4.
6. **LEO's confounder is drag, as GEO's was libration** (§7.2). It is not
   modelled by a robust local trend, and any T8 detector that matters in LEO
   will have to model geomagnetic-driven density variation explicitly.

---

## 13. Reproduction

```
# the registration, committed ALONE, before any measurement code existed
git show 23d4776 --stat

# the instrument and its tests
python3 -m unittest tests.test_orbit_proximity_plane          # 74 tests
python3 tools/proximity_plane.py --stage extract   --work $W  # 757 s
python3 tools/proximity_plane.py --stage detect    --work $W  # 323 s
/home/sdegan/gpu-broker/gpu-run --estimate-mib 900 --class standard -- \
  .venv-gpu/bin/python tools/proximity_plane.py --stage bench --work $W
python3 tools/proximity_plane.py --stage analyze --regime LEO --label primary --work $W
python3 tools/proximity_plane.py --stage nulls   --regime LEO --label primary --work $W
```

Determinism: seed 20260922 for the permutation null, the time shuffle and any
subsampling; no other randomness. Source hashes of the instrument, its tests,
the registration and every pipeline module imported are in
`docs/proximity-leo-20260922-receipt.json` under `sourceSha256`
(`tools/proximity_plane.py` = `7f8ad845…a0cc72`). The receipt also carries the
full summary of every threshold arm, including the six whose event catalogues
are not committed for size; each is reproduced by one `--stage analyze` call
with its `--theta-p`, `--gamma` or `--d-days`.

Nothing from T8b was written to `src/`, `data/`, `public/` or any site surface.
Publication and site framing for this track is reserved to Sean.
