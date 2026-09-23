# T21 results — differential (common-mode-rejecting) manoeuvre detection: the common mode is not there

**VERDICT. The hypothesis is REFUTED on its own registered falsifier, in both arms and on every
control. Two spacecraft flying the same orbit share almost none of the element-set error their
detector reacts to (the scoping is §13's, and it is the honest one):
measured on 447 near-coincident element-set pairs with nothing interpolated, the correlation
between Sentinel-3A's and Sentinel-3B's detector residuals is ρ = 0.023, 95% [−0.056, 0.407] —
registered falsifier F1 requires an upper bound above 0.500 to survive, and it FIRES. The
registration derives R = √(2(1−ρ)), so differencing can only help when ρ > ½; at ρ = 0.023 it
predicts a differential 1.40× NOISIER. At the shipped detector's own false-flag rate the
differential arm recalls 3 of 241 Sentinel-3 manoeuvres against the single-object arm's 8 —
an increment of −2.07 points, 95% [−5.76, 0.00] — and F3 fires. A NON-co-orbital control 17 km
lower, SARAL, correlates with Sentinel-3A EIGHT TIMES more strongly (ρ = 0.196, passband-matched
95% [0.004, 0.365]) than Sentinel-3A's own co-orbital twin does, so P3 fires too: whatever common
mode exists is not the co-orbital one. At GEO, over 1,151 of T11's co-located episodes, the
east–west differential floor is 0.926× the single-object floor, 95% [0.833, 0.995] — a real but
7% reduction — while the north–south differential is 1.439× WORSE, which is √2 to within 2%, the
value the derivation gives for no common mode at all.**

**And the reason the method cannot help is measured, not guessed.** The Sentinel-3 pair's
detector noise floor is **1.25 m (3A) and 2.77 m (3B) of semi-major axis** at five sigma — 40 to
100 times below the shipped detector's published 102–126 m floor. Yet to reach the shipped
detector's own false-flag rate the single-object detector needs a multiplier of **2,544**, not 5,
putting its operating floor at **274 m**. The operating floor is therefore **not set by noise**.
It is set by real, non-manoeuvre variation in these spacecraft's element series, and differencing
a noise term that is already 200× below the binding term cannot move it.

**Registration:** `docs/t21-differential-preregistration-20260923.md`, committed **alone** at
`ca7ce73` before any T21 number and before any T21 code existed, and amended **alone** once at
`664d039` (two words on the programme's own ban list; no threshold, screen, decision rule or gate
changed). **Instrument:** `tools/differential_detect.py`, committed with its 23 offline proofs at
`4afe4ef`, still before any number. **Artefact:** `docs/t21-differential-results-20260923.json`.
**Host:** `pc`, CPU only, `nice -n 15`; whole run **25.05 s**, peak RSS 1.57 GiB. No GPU stage was
declared and none was used.

---

## 0. Read the floors first

| Floor | Value | Source |
|---|---|---|
| Shipped LEO detector floor, pooled σ arm | 102.2 – 126.0 m of *a* (54.0 – 58.7 mm/s) | T16b §3.1 |
| Shipped LEO detector floor, per-object σ arm | 50.0 m, pinned by the `DA_FLOOR_KM` constant | T16b §3.1 |
| Shipped detector recall, eleven spacecraft | 90/1134 = **7.937%** [6.502, 9.656] | `t16b-truthset-recall-20260922.json` |
| Shipped detector false-flag rate | **0.012642669** flags/quiet-window-day | `t18-floor-20260922.json` |
| Cadence-only schedule floor, eleven spacecraft | **5.115%** [3.977, 6.555] | T18 §0 |
| **Shipped, Sentinel-3A + 3B only** | **10/292 = 3.425%** (3A 2/147, 3B 8/145) | same file, `bySpacecraft` |
| **Schedule floor, Sentinel-3A + 3B only** | **5/292 = 1.712%** (3A 0/147, 3B 5/145) | same file, `bySpacecraft` |

Both two-spacecraft rows are reproduced exactly by this instrument on the full 292 labels
(10/292 and 21/292 for the per-object arm), which is the cheapest available evidence that T21 is
measuring the same thing T16b measured.

**The pooled eleven-spacecraft numbers do not compose with a two-spacecraft number** and are never
used as the increment's base. §7 binds this.

---

## 1. The pair, measured — and one correction to the brief

Registration §3.1 required the pair's geometry to be measured rather than assumed. Over **4,628
element-set pairs whose epochs differ by less than 0.05 days** (median offset 0.027 d), with the
residual offset closed by propagating the mean anomaly at each object's own mean motion:

| | measured |
|---|---|
| median semi-major axis, 3A / 3B | 7180.796 / 7180.797 km |
| **median Δa** | **−1.80 m** |
| **median Δi** | **−0.0042°** |
| **median ΔRAAN** | **−0.0063°** |
| orbital period | 6055.78 s |
| **median along-track phase difference** | **−139.80°**, quartiles [−140.63, −138.46] |
| **median along-track separation** | **2,352 s = 39.2 minutes** |
| element sets, 3A / 3B | 14,762 / 5,647 |
| median element-set spacing, 3A / 3B | 0.281 d / 0.421 d |

**The conductor's brief states the two spacecraft are "~140 s apart". The measured separation is
140 DEGREES — 2,352 seconds, 39 minutes.** They share a plane to six thousandths of a degree and a
semi-major axis to 1.8 m, so they are genuinely co-orbital; they are not adjacent. Nothing in this
document depends on the brief's figure, and the correction is recorded because a reader who
believed 140 s would expect the two to sample the same atmosphere at the same instant. At 39
minutes apart they are a third of an orbit away from one another, which is *consistent with* the
near-zero correlation measured in §3 and is offered as an interpretation, not as a demonstrated
mechanism.

---

## 2. Interpolation, measured before anything else (gate G2)

Hold-one-out: every interior element set rebuilt from its two neighbours.

| | interior sets | refused for gap (> 5 d) | median \|error\| | MAD σ |
|---|---:|---:|---|---|
| Sentinel-3A | 14,760 | 2 | 1.178e-7 rev/day = **0.040 m of *a*** | 1.746e-7 = 0.059 m |
| Sentinel-3B | 5,645 | 4 | 2.100e-7 rev/day = **0.070 m of *a*** | 3.113e-7 = 0.104 m |

The interpolation error is **0.04–0.07 m of semi-major axis** — thirty to seventy times below the
5σ noise floors of §3 and three to four orders below any operating threshold. **Interpolation is
not what limits this measurement.**

**Gap refusal is not symmetric and it matters.** Building the differential on Sentinel-3A's epochs
requires a Sentinel-3B bracket, and **2,965 of 3A's 14,762 epochs (20.1%) have none**; the reverse
direction refuses **1 of 5,647**. That asymmetry is the sparser object's cadence, and it is why
gate G4 fires (§6).

**The differential residual is strongly autocorrelated**: lag-1 **0.846** (host 3A) and **0.766**
(host 3B). The shipped detector's two-consecutive-sample confirmation rule assumes a lone bad fit
produces one excursion; at this autocorrelation it does not, and that is part of why the
differential arm needs an extreme multiplier to reach any usable false-flag rate (§5).

---

## 3. The correlation — the number the whole hypothesis rests on

Registration §2.2: with r_X = c + ε_X, ρ ≡ Corr(r_A, r_B) = σ_c²/(σ_c²+σ²), and

> **R = √(2(1 − ρ))**, so differencing lowers the floor **if and only if ρ > ½**.

Measured on Sentinel-3A/3B, on labelled-quiet intervals, three ways:

| ρ, measured | value | 95% (30-day block bootstrap, 1,000 resamples, seed 20260923) | pairs |
|---|---:|---|---:|
| **near-coincident element sets, nothing interpolated** | **0.0230** | **[−0.056, 0.407]** | 447 |
| passband-matched (5-day window on both, nothing interpolated) | 0.0352 | [−0.020, 0.429] | 447 |
| through interpolation onto 3A's epochs | 0.0175 | [−0.022, 0.202] | 1,168 |

**The first row is the primary measurement**, because it needs no interpolation at all. The second
exists because the shipped residual filter uses a window of ten *samples*, and two objects with
different cadences therefore get different time windows — a genuinely common error could show a low
correlation for that reason alone. Setting both windows to the same **5 days** raises ρ from 0.023
to 0.035 and moves nothing.

**Registered falsifier F1: is ρ's 95% upper bound ≤ 0.500? YES, on both interpolation-free
measurements (0.407 and 0.429). F1 FIRES.**

Derived from ρ = 0.023: **R = 1.398** — the differential should be 40% noisier. The two members do
not carry equal noise (σ_3B/σ_3A = **1.975**), so the generalised unequal-variance form of the same
derivation, referenced to 3A, gives **R = 2.193**.

---

## 4. The floors — what actually moved, and why the model is reported wrong

Five sigma on the measured noise, with the 50 m constant and the drag term dropped (the registered
instrument change of §3.5, labelled everywhere it is used):

| host | quiet samples | σ single | σ differential | **R measured** | 95% | floor single | floor differential |
|---|---:|---|---|---:|---|---:|---:|
| **Sentinel-3A** | 1,168 | 7.479e-7 | 7.727e-7 | **1.033** | [0.853, 1.262] | **1.25 m** (0.65 mm/s) | 1.30 m (0.67 mm/s) |
| **Sentinel-3B** | 550 | 1.652e-6 | 9.949e-7 | **0.602** | [0.483, 0.765] | **2.77 m** (1.44 mm/s) | 1.67 m (0.87 mm/s) |

**Registered screen P1, both clauses:**

- *Does the floor move?* On host 3A, **no** — R's interval contains 1. On host 3B, **yes** — R's
  upper bound is 0.765.
- *Does the measured R agree with the derived one within a factor 1.25?* **NO on either host.**
  3A: 1.033 against a derived 1.398 — a ratio of 0.739. 3B: 0.602 against a derived 2.193 — a ratio
  of 0.275. **P1's model-agreement clause fails, and the registration says in advance what that
  means: the claim is WITHHELD regardless of the other screens, because a floor that moves for a
  reason the model does not contain is not evidence for the model.**

**What did move host 3B's floor, then.** Sentinel-3B carries 5,647 element sets to Sentinel-3A's
14,762, so the shipped ten-sample residual window spans 4.2 days on 3B against 2.8 days on 3A.
Over the longer window the local linear baseline fits the orbit less well, and 3B's residual
carries real orbital curvature that 3A's does not. Differencing against 3A's denser series removes
that curvature. **That is a sampling effect, not a cancellation of a shared error**, and it is
distinguishable from the hypothesis precisely because ρ is 0.023: nothing correlated was removed.
The mechanism is consistent with every cell above and with the smoothness limit the instrument's
own tests assert (§8), and it is offered as an interpretation, not as a proven mechanism.

**The shipped floor is 40 to 100 times above this pair's measurable noise.** T16b established that
the shipped 102–126 m is set by a pooled population σ and the per-object arm's 50 m by a chosen
constant. Measured here, this pair's own five-sigma noise floor is **1.25 m and 2.77 m**. A
detector could in principle see a 1.25 m semi-major-axis step on Sentinel-3A — except that it
cannot, for the reason §5 measures.

---

## 5. Detection at a matched false-flag rate

**The quiet-window denominator, and a registered fallback that fired.** The registration's
denominator is the **intersection** of the two spacecraft's labelled-quiet windows. It totals
**29.94 window-days over 42 windows** — below the registered 50-day bar — so the registration's own
fallback to the **union** is used: 292 windows, **365.00 window-days**. This is named here because
the union contains intervals in which only one of the two is labelled quiet, which makes the
false-flag denominator more permissive than the registered one. Gate G7 did not fire.

**Deviation: the registered sweep grid could not reach the operating point and was extended.** The
registration fixed k ∈ [1, 12] in steps of 0.25. On these objects the measured σ is so small that
no multiplier below 12 comes within two orders of magnitude of the shipped false-flag rate — the
shipped pooled σ is itself about 420 of Sentinel-3A's own σ. The grid was extended geometrically to
2×10⁶. This is a departure from the registered text and is recorded in §9. **The registered
tie-break — the smallest threshold whose false-flag rate does not exceed the stated rate — is unchanged,
and every arm is swept as one detector with one multiplier over both series**, after a first pass
that swept each series separately to the full rate budget and thereby doubled the arm's rate.

| arm | k | achieved rate | operating floor | **recall, 241 evaluable labels** | Wilson 95% |
|---|---:|---:|---:|---|---|
| S1 shipped, untouched | — | 0.016438 | 102–126 m | **8/241 = 3.32%** | [1.69, 6.41] |
| S2 per-object σ, untouched | — | 0.019178 | 50 m | **19/241 = 7.88%** | [5.11, 11.98] |
| S3 single, swept to the registered rate | **2,543.9** | **0.010959** | **273.8 m** | **8/241 = 3.32%** | [1.69, 6.41] |
| **D3 differential, swept to the registered rate** | **45,459.4** | **0.010959** | **3,698.1 m** | **3/241 = 1.24%** | [0.42, 3.60] |
| S3 single, swept to the shipped arm's own rate here | 1,097.2 | 0.016438 | 118.1 m | 8/241 = 3.32% | [1.69, 6.41] |
| **D3 differential, same** | 34,692.7 | 0.013699 | 2,822.2 m | **7/241 = 2.90%** | [1.41, 5.87] |
| D1 differential at the shipped multiplier k = 5 | 5 | **1.200000** | — | 219/241 = 90.87% | [86.57, 93.89] |

The last row is printed for one reason: at k = 5 the differential flags almost every label, at a
false-flag rate **95 times** the shipped detector's. A recall of 90.9% at that rate is not
detection, it is flagging.

**The increment, paired 90-day block bootstrap, 1,000 resamples, seed 20260923:**

| comparison | increment | block 95% | label 95% | minimum detectable |
|---|---:|---|---|---:|
| **D3 − S3, at the registered rate** | **−2.07 pts** | **[−5.76, 0.00]** | [−4.56, +0.41] | 2.88 pts |
| D3 − S3, at the shipped arm's own rate here | −0.41 pts | [−2.64, +2.21] | [−2.07, +1.24] | 2.43 pts |

**Registered falsifier F3: is the increment's 95% upper bound ≤ 0? On the arm of record — the
block bootstrap at the registered operating point — the upper bound is 0.000, reached at the
boundary: in 1,000 resamples the differential never beat the single-object arm. F3 FIRES.** The
label bootstrap's upper bound is +0.41, and both are reported; the registration named the block
bootstrap as the arm of record before any of this existed, and the reading does not change if the
looser interval is preferred, because that interval straddles zero and the registration reads a
straddling interval as NOT DEMONSTRATED.

**The minimum detectable increment is 2.88 points.** An increment of −2.07 points could not have
been *demonstrated* by this design in either direction. What the design does demonstrate is the
absence of a gain: the registered aim was a recall exceeding the single-object arm's, and the
measured point estimate has the wrong sign at both operating points.

**Increments against the population-matched published floors** (the differential arm at the
registered rate, 1.24%): against the shipped **3.425%**, −2.18 points; against the schedule floor
**1.712%**, −0.47 points. Against the pooled eleven-spacecraft **7.937%** and **5.115%** the
differences are −6.70 and −3.88 points, printed as cross-population reference and **not** as
increments.

**By burn size, at the registered rate** (archive-bracketed |Δa|, a stratifier and never evidence):

| \|Δa\| bin | labels | S1 shipped | S3 single swept | D3 differential |
|---|---:|---:|---:|---:|
| < 20 m | 69 | 2 | 2 | 1 |
| 20–50 m | 150 | 0 | 0 | 0 |
| 50–100 m | 9 | 0 | 0 | 0 |
| 200–500 m | 2 | 1 | 1 | 0 |
| ≥ 500 m | 11 | 5 | 5 | 2 |

The differential loses in every bin that has any hits at all. There is no stratum in which it wins.

**The term the swept arms dropped was doing the work.** S2 — the shipped detector at each object's
own σ, with the 50 m constant and the object's own drag term kept — recalls **19/241 = 7.88%** at a
rate of 0.0192, beating both swept arms at comparable rates. The drag term adapts the threshold to
the object's own recent rate of change, which is exactly the non-manoeuvre variation that sets the
operating floor. **Removing it cost more than differencing could ever have returned**, and that is
a result about the shipped detector rather than about the differential.

---

## 6. The controls — and the one that refutes the premise directly

All ρ below are the interpolation-free coincident measurement and the passband-matched one; R is
the operational floor ratio with its 30-day block interval.

| control | ρ (coincident) | ρ (passband-matched), 95% | **R** | 95% |
|---|---:|---|---:|---|
| **Sentinel-3B (the co-orbital partner)** | **0.023** | **0.035** [−0.020, 0.429] | 1.033 (host 3A) | [0.853, 1.262] |
| **C1 — SARAL**, 7163.0 km, non-co-orbital | **0.196** | **0.195** [**0.004**, 0.365] | **0.743** | [0.626, 0.871] |
| C2 — CryoSat-2, 7096.7 km | 0.080 | 0.114 [−0.003, 0.322] | 0.934 | [0.772, 1.083] |
| C3 — Sentinel-3B, epochs shifted +180 d | −0.009 | 0.004 [−0.085, 0.030] | **1.888** | [1.489, 2.496] |
| C3 — Sentinel-3B, epochs shifted −180 d | 0.008 | 0.012 [−0.138, 0.030] | **1.858** | [1.521, 2.296] |
| C3 — Sentinel-3B, residuals permuted | −0.002 | −0.006 [−0.031, 0.033] | 46.081 | [34.50, 60.23] |

C1 was chosen by the registered rule — *the other labelled spacecraft whose median semi-major axis
is closest to Sentinel-3A's* — resolved at run time to **SARAL**, 7163.0 km against Sentinel-3A's
7180.8 km, a difference of 17.8 km and a different orbit plane.

**Registered screen P3 fails, and it fails in the most informative way available.** SARAL is not
co-orbital, and it correlates with Sentinel-3A **eight times** more strongly than Sentinel-3A's own
co-orbital twin does — and it is the **only** object whose passband-matched ρ has a 95% lower bound
above zero. Its floor ratio, 0.743 [0.626, 0.871], is a larger reduction than the co-orbital
partner delivers on the same host. The registration wrote down in advance what this means: the
*co-orbital* premise is wrong, and any residual common mode is not the one the hypothesis names.
It is a small effect either way — ρ = 0.196 is still far below the ½ the method needs.

**C3 behaves exactly as derived.** Destroying the time alignment drives ρ to zero and R to
1.86–1.89, against the √2 = 1.414 the derivation gives for ρ = 0 plus the extra cost of
differencing against a series whose secular trend no longer matches. The permuted arm's R of 46 is
the same statement with no structure left at all. **The instrument responds to the presence and
absence of a common mode; there is simply almost none between these two spacecraft.**

---

## 7. The sign question and the attribution rule

**The direction screen, measured before the rule is read** (registration §3.9): the fraction of
labels whose signed archive-bracketed Δa is positive is **87.8%** on Sentinel-3A (median +21.4 m)
and **87.6%** on Sentinel-3B (median +23.1 m). Both clear the registered 70% bar, so the rule is
**usable**: a confirmed negative step in Δn = n_3A − n_3B attributes to Sentinel-3A, a positive step
to Sentinel-3B.

**Measured against the labels, on flags falling inside exactly one spacecraft's event window:**

| arm | unambiguous flags | named correctly | accuracy | Wilson 95% |
|---|---:|---:|---:|---|
| at the matched operating point | **2** | 2 | 100% | [34.2, 100] |
| at the shipped multiplier k = 5 | **691** | 451 | **65.3%** | **[61.6, 68.7]** |

**The sign rule works — and there is no operating point at which it is useful.** At the matched
rate the differential raises two unambiguous flags in a decade, and nothing can be concluded from
two. At k = 5 there are 691 of them and the rule beats the 50% chance level decisively, but k = 5
is a false-flag rate 95× the shipped detector's, so that cell measures **the rule**, not a
detector. Both rows are printed because printing only the second would be reporting a capability
that no usable detector possesses.

---

## 8. The GEO arm — T11's co-located pairs

Gate G8 discharged: T8a's near-GEO extract matches its three pinned counts (217,007,154 scanned,
11,626,494 kept, 1,768 objects). **1,151 of T11's 1,317 committed episodes** carry enough element
sets on both members and enough quiet samples to measure; the rest are reported as unused rather
than filled in. Interpolation: 1,696 of 307,753 output epochs refused for gap; hold-one-out median
|error| **5.84e-5 deg/day** (MAD σ 8.66e-5), against an east–west flag floor of 0.010 deg/day.

**There is no manoeuvre truth at GEO.** "Quiet" here means *no single-object flag from either
member within ±7 days* — a chosen screen, not an operator's declaration — and the word *recall*
does not appear in this section.

### 8.1 The floor

| | median | 95% | derived from ρ |
|---|---:|---|---:|
| **ρ**, per episode | **0.1619** | [0.1401, 0.1783] | — |
| **R, east–west** (drift rate) | **0.9259** | **[0.8333, 0.9953]** | 1.2947 |
| **R, north–south** (inclination rate) | **1.4389** | [1.3581, 1.5136] | 1.2947 |

East–west R quantiles across episodes: p10 **0.144**, p25 0.373, p50 0.926, p75 1.515, p90
**2.213** — a spread of fifteen to one.

**The east–west differential floor is 7.4% lower than the single-object floor**, with a 95% upper
bound of 0.9953, just below 1. **The model disagrees with it**: a ρ of 0.162 derives R = 1.295,
and the measured 0.926 is 0.715 of that — outside the registered 1.25 agreement factor. Per §5.4
the GEO floor claim is therefore **WITHHELD**, on the same clause that withheld it at LEO.

**The north–south channel is the derivation's cleanest confirmation in this document.** Measured
R = 1.439 against the √2 = 1.414 that the derivation gives for **no common mode at all** — agreement
to 1.8%. Differencing inclination rate between two co-located GEO objects adds noise in exactly the
amount the model says independent noise should add. F1's condition (ρ 95% upper bound 0.178 ≤ 0.500)
holds at GEO as well.

### 8.2 Agreement and lift — not accuracy

| channel | differential flags | with a single-object flag within ±2 d | ±30-day-shifted control | **lift** |
|---|---:|---|---|---:|
| **east–west** | 5,212 | **71.57%** [70.33, 72.77] | 35.55% [34.51, 36.62] | **2.01×** |
| **north–south** | 14,914 | 23.10% [22.43, 23.78] | 17.63% | **1.31×** |

Reverse direction, east–west: only **5,227 of 14,864 single-object flags (35.17%)** have a
differential flag within ±2 days. **The differential sees a third of what the single-object
detector sees, and adds flags of its own that are right about twice as often as chance.** That is a
descriptive statement about two flag streams, it is not an accuracy, and no GEO number here may be
read as one.

---

## 9. Gates, and the deviations

| Gate | Verdict |
|---|---|
| **G1** detector untouched | **discharged** — `git diff` over `tools/proximity_plane.py` and `tools/proximity_geo.py` empty; blob hashes in the results JSON |
| **G2** interpolation error printed first | discharged — §2 precedes every detection cell |
| **G3** floors printed first | discharged — §0, §3 and §4 precede §5 |
| **G4** evaluability | **FIRED** — 51 of 292 labels (17.5%) have no usable differential sample. The registered consequence is applied: **every** arm, including the shipped ones, is scored on the same 241, and the shipped arms carry their all-292 cells beside them (10/292 and 21/292, both reproducing the published values) |
| **G5** tests | discharged — 23 offline proofs, all pass |
| **G6** sample | did not fire — 1,168 usable quiet samples against a bar of 200 |
| **G7** operating point | did not fire — but the registered **intersection** denominator is only 29.94 window-days, below the 50-day bar, so the registration's own **union fallback** is used (365.00 window-days) and is named wherever a false-flag rate is printed |
| **G8** GEO input | discharged — all three pinned counts match |

### Deviations from the registration

1. **The sweep grid was extended** from the registered k ∈ [1, 12] to 2×10⁶ (§5). On these objects
   no multiplier below 12 comes within two orders of magnitude of the operating point, so the
   registered grid could not answer the registered question. The tie-break rule is unchanged.
2. **Arms are swept as one detector over both series**, with one multiplier, rather than each
   series independently. A first pass did the latter and produced an arm whose pooled false-flag
   rate was twice its own budget; the defect was found by reading the achieved rates against the
   stated rate, and every number was recomputed after the fix.
3. **A second operating point was added**, post-registration and labelled: the shipped arm's own
   false-flag rate **on these windows** (0.016438), beside the registered pooled 0.012642669 which
   was measured over eleven spacecraft's windows. Both are reported; the registered one is the arm
   of record and the verdict does not change between them.
4. **Two further ρ measurements were added**, post-registration and labelled (§3): the
   interpolation-free coincident-epoch measurement, which is the primary one, and the
   passband-matched one. The registration's method measured ρ through an interpolation of the
   sparser object onto the denser one's epochs, which smooths away exactly the high-frequency
   component whose correlation is in question. All three are printed and they agree.
5. **The floor ratio is reported two ways** (§4 and the JSON's `ratioNote`): the difference of the
   two residuals, which is the quantity the §2.2 model predicts and which carries the P1 derivation
   check, and the residual of the differential, which is the series the detector consumes and which
   carries the floor. The rolling Theil–Sen residual is a median-based, non-linear filter, so the
   two are not the same series.
6. **The generalised unequal-variance form of the derivation was added** (§3). The registration
   assumed equal variances and said §5 would register what happens if the measurement contradicted
   that; the measurement does — σ_3B/σ_3A = 1.975 — and the generalised form is printed beside the
   equal-variance one.
7. **Attribution is reported at two operating points** (§7) rather than one, because the registered
   one raises two unambiguous flags.

Nothing else departed from the registration, and the registration was not edited after the
amendment at `664d039`, which itself preceded every number.

---

## 10. What these numbers may not be used for

- **The LEO arm is two spacecraft and one operator.** Sentinel-3A and 3B share a ground segment, an
  orbit-determination process and a manoeuvre-planning system. Their 292 labels are not independent
  of one another. A null measured on this pair is a statement about **this pair**; it does not prove
  that no co-orbital pair anywhere shares element-set error.
- **Two clusters is not enough for an object-clustered interval**, so the arm of record is a
  90-day time-block bootstrap, with its limitation stated wherever its interval appears.
- **The minimum detectable increment is 2.88 points.** This design could not have demonstrated a
  smaller increment in either direction.
- **The pooled eleven-spacecraft 7.937% and 5.115% do not compose** with a two-spacecraft recall.
- **MAD-LEO's labelled-quiet windows are mined from a TLE archive, not declared quiet by an
  operator**, so every false-flag count is an upper bound and the phrase "false-alarm rate" is not
  used. The union fallback (§5) makes this denominator more permissive still.
- **GEO has no truth.** Agreement is agreement; nothing in §8 is an accuracy.
- **Every threshold here is a chosen screen, not a physical law** — the 5σ multiplier, the 50 m and
  0.010 deg/day and 0.01° floors, the ±7-day quiet screen, the ±2-day agreement window, the 1.25
  model-agreement factor, the 0.500 correlation bar, the 5-day gap refusal, the burn-size bins, the
  180-day epoch shift, the 70% direction-screen bar, the 0.05-day coincidence tolerance.
- **The 39-minute along-track separation is offered as consistent with the measured ρ, not as its
  demonstrated cause.** No mechanism for the absence of a common mode is proven here.
- **Nothing here is about constellations, about Starlink, or about any operator whose manoeuvre log
  is not public.**

---

## 11. The registered verdict, screen by screen

| Screen | Registered condition | Verdict |
|---|---|---|
| **P1** floor moves *and* model agrees | R upper bound < 1.000 **and** measured/derived within 1.25 | **WITHHELD** — moves on host 3B only (0.602 [0.483, 0.765]), not on 3A (1.033 [0.853, 1.262]); model agreement 0.739 and 0.275, both outside the factor |
| **P2** recall rises at matched rate | paired lower bound above zero | **FAILS** — increment −2.07 pts, block 95% [−5.76, 0.00] |
| **P3** controls separate | no control's R upper bound below 1.000 | **FAILS** — SARAL, not co-orbital, gives R = 0.743 [0.626, 0.871] and eight times the correlation |
| **F1** ρ upper bound ≤ 0.500 | refutes | **FIRES** — 0.407 (coincident), 0.429 (passband-matched), 0.178 (GEO) |
| **F2** R lower bound ≥ 1.000 | refutes | **does not fire** — neither host's R has a 95% lower bound at or above 1.000 (3A [0.853, 1.262], 3B [0.483, 0.765]) |
| **F3** increment upper bound ≤ 0 | refutes | **FIRES** at the boundary — 0.000 on the arm of record |
| **§5.4** GEO floor claim | R upper bound < 1 **and** model agrees | **WITHHELD** — 0.926 [0.833, 0.995] but measured/derived 0.715 |

**Two of the three falsifiers fire and none of the three claim-clauses is met. The registered
reading is that differential detection does not lower the manoeuvre-detection floor on this pair,
and the reason is measured: there is no common mode to reject.**

---

## 12. What this changes for the programme

1. **The programme now has a measured number for how much of the element-set error a detector
   reacts to is shared between two objects on the same orbit: 2.3%, 95% upper bound 40.7%.** That number closes a
   family of proposals, not just this one — any method whose gain comes from cancelling a shared
   element-set error between catalogued objects is working against a term that is, on the best
   test case available, almost absent.
2. **The LEO detector's operating floor is not a noise floor.** This pair's five-sigma noise floor
   is 1.25–2.77 m of semi-major axis; the multiplier needed to reach the shipped false-flag rate is
   2,544, putting the operating floor at 274 m. **The binding term is real non-manoeuvre variation,
   not noise**, and T16b's finding that 86% of these operators' burns fall below the shipped floor
   is therefore not a calibration problem that a quieter statistic can fix.
3. **The shipped detector's own drag term is load-bearing.** Dropping it, as the swept arms did by
   registration, cost more recall (7.88% → 3.32% at comparable rates) than any differencing scheme
   returned. That is a candidate for its own registration: the per-object arm at 50 m already
   recalls 7.88% on this pair against the shipped arm's 3.32%, at a false-flag rate 1.17× higher.
4. **At GEO the east–west differential is worth 7% of the floor and a 2.01× agreement lift**, and
   the north–south differential is 1.44× worse. Neither supports a detector change; the east–west
   number is the only cell in this document where the differential is measurably better than the
   single-object series at anything, and its model check fails.
5. **The Sentinel-3 pair's geometry is 140 degrees, not 140 seconds.** Any future proposal that
   assumes the pair samples the same atmosphere simultaneously needs to be re-derived.

**OWED:** the S2-versus-S1 result of §5 (per-object σ recalls 19/241 against the shipped arm's
8/241 on this pair) is a measured, cheap improvement to the shipped LEO detector and belongs in its
own registration, not in this one; T16b §8.3 already flagged the same thing on eleven spacecraft and
it is still unregistered.

---

## 13. The adversarial pass

Registration §8.4 requires one adversarial read before the track is discharged, under a prompt that
states in advance that **sustaining the conclusion unchanged is a complete and expected response,
and that a challenge is pressure, not evidence.** Five challenges were put; four were answered from
cells this document already contains; one produced a real scoping correction, recorded below and
folded into §3. Outcome: **revised** — the verdict is unchanged, one clause is narrowed.
Ledger: `docs/t21-capitulation-ledger-20260923.jsonl`.

**C-1 (sustained, and it changed a clause). "ρ = 0.023 does not prove the two objects share no
error. The rolling Theil–Sen residual removes a local linear fit over the preceding ten samples —
2.8 days on Sentinel-3A. A common mode with a correlation time much longer than that is removed
from BOTH residuals before ρ ever sees it, so a large shared density error could hide behind a
near-zero ρ."**

This is correct, and the claim is narrowed accordingly. **What is measured here is the correlation
of the error the detector actually reacts to** — the residual after its own baseline — and not the
correlation of the raw element-set error. The narrowing costs the conclusion nothing, because a
shared error that the baseline removes cannot raise a flag in either arm and so cannot be what a
differential detector would be cancelling: the term a differential can help with is, by
construction, the term that survives the baseline. The passband-matched control (§3) doubles the
window to 5 days and moves ρ from 0.023 to 0.035, which bounds the effect over the range that
matters; beyond that the baseline itself, not the differential, is what suppresses the error. **The
sentence "two objects on the same orbit share almost none of their element-set error" is therefore
replaced throughout by "share almost none of the element-set error their detector reacts to".**

**C-2 (sustained unchanged). "F3 fires at a boundary — an upper bound of exactly 0.000 — and the
label bootstrap puts it at +0.41. You are reporting a refutation on a rounding."** Both intervals
are printed and the registration named the block bootstrap as the arm of record before any number
existed. The reading does not depend on the boundary: the point estimate is negative at **both**
operating points (−2.07 and −0.41 points), the differential loses in **every** burn-size bin that
has any hits, and the recall claim would fail on the looser interval too, which straddles zero and
which the registration reads as NOT DEMONSTRATED. No clause rests on the boundary.

**C-3 (sustained unchanged). "SARAL's higher correlation is a cadence artefact: it simply samples
more like Sentinel-3A than Sentinel-3B does."** The passband-matched measurement equalises the time
window across objects, and SARAL keeps ρ = 0.195 with a 95% lower bound of 0.004 — the only
non-zero lower bound in the control table. The effect survives the control built for exactly this
objection.

**C-4 (sustained unchanged). "You dropped the drag term from the swept arms, so you crippled the
comparison."** Both swept arms dropped it, by registration and symmetrically, and the result of
that choice is reported as its own finding (§5, §12.3) rather than hidden: the shipped detector
with the drag term kept beats both swept arms. The differential-versus-single comparison is
internally like-for-like at every operating point printed.

**C-5 (sustained unchanged). "A different differential channel — Δa directly, or a smarter
estimator — might have worked."** Possibly, and this document does not claim otherwise. What is
measured is that the term such a scheme would exploit is, in the detector's own residual channel,
2.3% of the variance with a 95% upper bound of 40.7%, against the 50% the arithmetic requires. That
bound constrains any estimator that works by cancelling a shared term, not only this one.
