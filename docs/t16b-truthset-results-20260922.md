# T16b results — the truth set: measured element error growth, and the programme's first measured recall

**Registration**: `docs/t16b-truthset-preregistration-20260922.md`, committed
alone before any number was computed (9df7675).
**Artefacts**: `docs/t16b-truthset-growth-20260922.json`,
`docs/t16b-truthset-recall-20260922.json`.
**Instruments**: `tools/truthset_fetch.py`, `truthset_truth.py`,
`truthset_sgp4.mjs`, `truthset_growth.py`, `truthset_recall.py`;
26 tests in `tests/test_truthset.py`.

---

## 0. The two numbers

**(A)** Over calendar 2023, an element set from this archive propagated with
the programme's own SGP4 has a **median along-track error of 0.32–0.69 km at
+1 d, 2.1–7.1 km at +7 d, 90–99 km at +30 d and 844–876 km at +90 d**, on
Sentinel-1A, Sentinel-3A and Sentinel-3B against their own precise orbits.
The median along-track error crosses **T8b's co-orbital station threshold
(Γ = 5°, 617–627 km at these radii) at +75.8 to +76.7 days**, and crosses the
tightest registered arm (Γ = 0.2085°, 25.8–26.1 km) at **+14.5 to +16.7 days**.

**(B)** Run at its shipped settings over 1,134 operator-reported manoeuvres of
eleven geodetic and altimetry spacecraft, the programme's LEO burn detector
flags **90 — a recall of 7.94%, Wilson 95% [6.50, 9.66]** — against **18 flags
inside 1,139 labelled-quiet windows** (1,424 window-days). Split at the
detector's own measured floor, the same 1,134 labels give **51.6%
[43.8, 59.3] above the floor** and **0.9% [0.5, 1.7] below it**: the number is
not a detector that misses, it is **a detector that cannot see 86% of what
these operators actually do**, because 977 of the 1,134 manoeuvres move the
semi-major axis by less than the 102–126 m the shipped threshold requires.

Both are benchmarks on eleven cooperative, well-tracked spacecraft. Neither is
a census, and §6 says what they may not be used for.

---

## 1. What was fetched, and what could not be

| Role | Product | Fetched |
|---|---|---|
| Truth, Sentinel-1A | Copernicus **AUX_POEORB** (Earth Explorer XML), EARTH_FIXED, UTC, 10 s | **367 daily products, 1.71 GB**, AWS `s1-orbits`, anonymous |
| Truth, Sentinel-3A / 3B | **CNES/SSALTO POE SP3-c version 30 (POE-G)**, ITRF, TAI, 60 s | **41 / 42 arcs**, 25.9 / 26.5 MB, IDS FTP, anonymous |
| Earth orientation | IERS `finals2000A.all` | 3.8 MB |
| Labels | **MAD-LEO** mission-reported annotations, CC BY 4.0, doi 10.6084/m9.figshare.33446503.v1 | 5 CSV tables, 1.4 MB, kept on the analysis host, not redistributed |
| Manoeuvre notices | IDS/DORIS `s3aman.txt`, `s3bman.txt` | current to 2026-09-11 / 2026-08-26 |

Every file's URL, byte count and SHA-256 is in `manifest-*.json` on the
analysis host.

***The Sentinel-2 precise orbit product could not be fetched.*** The
Copernicus Data Space catalogue lists `S2A_OPER_AUX_POEORB_*.EOF` to an
anonymous query — name, size and checksum are returned — but the download
endpoint answers an anonymous request with HTTP 401 `Token not found`, and a
token requires an account this session does not hold; the ESA STEP auxiliary
mirror, which serves Sentinel-1 POEORB openly, has no Sentinel-2 tree
(HTTP 404). Sentinel-2 is therefore absent from (A) for want of a fetchable
truth product and for no other reason. Sentinel-1B is absent because the
spacecraft was lost in December 2021.

**Truth-product properties, measured from the files rather than quoted.**
Sentinel-1A AUX_POEORB **latency is 19.30 days** (p5 19.26, p95 19.30, from
creation time minus end of validity over all 367 products) with ~26 h of
validity per file; the Sentinel-3 POE arcs are **10 days each**, uniformly.
These are calibration products, not live ones — a fact that matters more to
this programme than their accuracy does.

**A correction to the T16 row.** The runbook described MAD-LEO as "6,785
Starlink objects, 107 h, 1,134 operator-evidenced manoeuvres". Those are two
different subsets. The **1,134 labels are from eleven geodetic and altimetry
spacecraft** (CryoSat-2, Sentinel-3A/3B, Jason-1/2/3, SWOT, SARAL, HY-2A,
TOPEX/Poseidon, Sentinel-6A), parsed from IDS/DORIS mission histories; the
Starlink subset carries **no manoeuvre labels at all** and its authors state
it is operator *prediction*, "never maneuver ground truth". No recall number
here is about Starlink or about any constellation.

---

## 2. Measurement (A) — how fast a propagated element set goes wrong

272 daily element sets per Sentinel (256 for Sentinel-3B) across
2023-01-01 → 2023-10-03, each propagated to +0/1/3/7/14/30/60/90 days and
differenced against the truth product's own nearest sample. 6,400 comparisons
planned, **none dropped** by the offset bar, **no propagator failures**.

### 2.1 Along-track error, median and tail (kilometres)

| Horizon | Sentinel-1A p50 | p95 | Sentinel-3A p50 | p95 | Sentinel-3B p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| **+0 d** | 0.582 | 2.189 | 0.577 | 0.707 | 0.330 | 0.730 |
| **+1 d** | 0.686 | 3.627 | 0.316 | 1.436 | 0.337 | 2.365 |
| **+3 d** | 2.000 | 8.054 | 0.984 | 9.393 | 0.793 | 9.929 |
| **+7 d** | 7.119 | 19.452 | 2.136 | 30.667 | 2.503 | 28.921 |
| **+14 d** | 24.064 | 60.212 | 18.088 | 71.144 | 20.718 | 72.539 |
| **+30 d** | 99.408 | 228.729 | 90.186 | 231.450 | 99.444 | 234.753 |
| **+60 d** | 383.154 | 915.603 | 379.808 | 738.646 | 397.466 | 748.516 |
| **+90 d** | 844.189 | 2017.070 | 869.100 | 1540.907 | 876.483 | 1631.866 |

### 2.2 The other two components, and the phase angle (medians)

| Horizon | radial (km) 1A / 3A / 3B | cross-track (km) 1A / 3A / 3B | along-track phase (°) 1A / 3A / 3B |
|---|---|---|---|
| +1 d | 0.132 / 0.015 / 0.026 | 0.229 / 0.146 / 0.176 | 0.0056 / 0.0025 / 0.0027 |
| +7 d | 0.140 / 0.188 / 0.191 | 0.483 / 0.165 / 0.147 | 0.0577 / 0.0170 / 0.0200 |
| +30 d | 0.617 / 1.450 / 1.564 | 1.338 / 0.729 / 0.654 | 0.805 / 0.719 / 0.793 |
| +90 d | 51.04 / 51.61 / 52.60 | 3.594 / 3.064 / 2.166 | 6.834 / 6.941 / 7.000 |

**The error is along-track and almost nothing else.** At +30 d the along-track
median is 68–160× the radial and 74–152× the cross-track. The plane is the
quiet direction, exactly as T8b's own plane-noise diagnostic (0.000148°
scatter) implied and as the site design assumed without measuring.

### 2.3 The horizon

`s = |r|·Γ·π/180` at each spacecraft's own measured mean radius:

| | mean radius | Γ = 5° | median crosses it | Γ = 0.2085° | median crosses it |
|---|---:|---:|---:|---:|---:|
| Sentinel-1A | 7075.4 km | 617.4 km | **+76.7 d** | 25.75 km | **+14.5 d** |
| Sentinel-3A | 7182.2 km | 626.8 km | **+76.7 d** | 26.14 km | **+16.7 d** |
| Sentinel-3B | 7182.2 km | 626.8 km | **+75.8 d** | 26.14 km | **+15.7 d** |

Log-log interpolation between the bracketing measured horizons, as registered.
Nothing is extrapolated.

### 2.4 The growth law, and what the site's ribbon gets right and wrong

From +30 d to +90 d the median grows by **8.5× / 9.6× / 8.8×** over a factor 3
of time, i.e. as **t^1.95 / t^2.06 / t^1.98** — quadratic. A constant
semi-major-axis error produces an along-track error *linear* in time; a
quadratic one is what a constant unmodelled **rate of change** of the
semi-major axis produces. That is the signature a propagator that knows
nothing of station-keeping should show on a satellite whose operator keeps
raising it, and it is offered as an interpretation consistent with the
exponent, not as a proven mechanism.

The orbits-section design draws the LEO ribbon from `σ_n` alone: 0.023 °/day
at the median, i.e. **linear**. Against the measurement:

| Horizon | ribbon (σ_n only) | measured median (1A / 3A / 3B) | verdict |
|---|---:|---|---|
| +1 d | 0.023° | 0.0056 / 0.0025 / 0.0027° | ribbon **4–9× too wide** |
| +7 d | 0.161° | 0.058 / 0.017 / 0.020° | ribbon **3–9× too wide** |
| +14 d | 0.322° | 0.195 / 0.144 / 0.165° | ribbon ~2× too wide |
| +30 d | 0.690° | 0.805 / 0.719 / 0.793° | **agrees, within 4–17%** |
| +60 d | 1.380° | 3.102 / 3.028 / 3.169° | ribbon **2.2× too narrow** |
| +90 d | 2.070° | 6.834 / 6.941 / 7.000° | ribbon **3.3× too narrow** |

So the σ_n ribbon is right at one horizon and wrong on both sides of it, for a
structural reason: it is linear and the error is quadratic. **The ribbon
should be redrawn from the measured quantiles, or labelled as a straight line
through a single crossing point.** (A design change, not made here.)

### 2.5 Manoeuvres inside the span

**Sentinel-3A/3B, manoeuvre-free arm** (no IDS-reported manoeuvre between the
element-set epoch and the comparison instant): the subset **runs out at
+14 d**, because these spacecraft manoeuvre roughly every two weeks (20 and 23
reported manoeuvres inside the 2023 truth window). Where it exists, it is much
smaller than the as-flown number:

| Horizon | 3A all / manoeuvre-free (km) | n free | 3B all / manoeuvre-free (km) | n free |
|---|---|---:|---|---:|
| +3 d | 0.984 / **0.909** | 229 | 0.793 / **0.647** | 204 |
| +7 d | 2.136 / **1.490** | 178 | 2.503 / **1.458** | 145 |
| +14 d | 18.088 / **5.181** | 91 | 20.718 / **3.540** | 59 |
| +30 d and beyond | — | **0** | — | **0** |

At +14 d the operator's own burns account for a factor **3.5** (3A) and
**5.9** (3B) of the median error. Neither manoeuvre-free series crosses either
Γ threshold inside the horizons where it still has data, and **no
extrapolation is given**.

**Sentinel-1A has no fetchable manoeuvre notice** (it carries no DORIS package;
`ids-doris.org` returns 404 for it), so it has no manoeuvre-free arm, and its
rows are as-flown only.

**The registered truth-derived screen returned nothing usable, and that is
reported rather than dressed up.** Counting days on which the truth's own
daily-mean *osculating* semi-major axis steps by more than MAD-LEO's 20 m
screen gives 276/369 days (Sentinel-1A) and 352/371, 352/380 (Sentinel-3A/3B)
— against 20 and 23 actual reported manoeuvres. The median day-to-day step is
32.6 m (1A) and 140 m (3A/3B), so the screen is far below the natural
variation of that statistic and **does not isolate manoeuvres**. MAD-LEO's
20 m is defined on a TLE bracket across a 30-hour window, not on this series;
transplanting it was the error, and the transplant is withdrawn. A
post-registration outlier rule on the same series (median + 5×MAD) finds 2, 2
and 1 days a year — also not the manoeuvre count. **The number of manoeuvres
Sentinel-1A performed inside the span is unmeasured here.**

### 2.6 Gate A4 fired

The +0 d residual — the element set differenced against truth at its own
epoch — has a median of **0.582 / 0.577 / 0.330 km**, against a +1 d median of
0.686 / 0.316 / 0.337 km. The registered clause asks whether the +0 d residual
is small against +1 d; it is not (ratios 1.18, 0.55, 1.02). **Gate A4 fires,
and the +1 d row is a floor measurement.**

What the floor is made of matters, and the registration asked the wrong
question. The +0 d residual is **not** this pipeline's noise:

- the frame chain's residual is derived at ≤ 0.1 m (§7), four orders below it;
- a timing error would be along-track and **identical in sign** on every
  spacecraft; the signed +0 d median is **+0.45 km on Sentinel-1A and
  −0.57 km on Sentinel-3A** — opposite signs, same pipeline;
- Sentinel-3A and 3B share a product, a parser and a frame chain and differ by
  1.7× (−0.570 vs −0.179 km).

The +0 d residual is therefore a property of **the element sets themselves** —
the along-track offset a GP fit carries at its own epoch, at the 0.3–0.6 km
scale. It is the right floor to print beside every row, and it is 3.4× below
the +3 d median and 1,450× below the +90 d median. Rows from +3 d on are not
floor-limited. **Deviation: the registered consequence ("the whole table is
reported as a floor measurement and nothing else") is applied to the +1 d row
only, with the diagnostic above given as the reason. That is a departure from
the registered text and is recorded as one in §5.**

Gates A1 (offset bar) and A2 (row counts) did not fire: 0 comparisons dropped,
every row n ≥ 256.

---

## 3. Measurement (B) — recall, the first one the programme has

### 3.1 The floor, printed first as registered

Per the derivation `|δa|min = (2/3)(a/n)·thr_n` and `Δv = δa·n_ang/2`:

| Arm | threshold set by | smallest detectable δa | smallest detectable along-track Δv |
|---|---|---|---|
| **pooled σ (shipped)** | `5σ_n`, the fit-noise term, on all eleven | **102.2 – 126.0 m** | **54.0 – 58.7 mm/s** |
| per-object σ | the **50 m** `DA_FLOOR_KM` term, on all eleven | **50.0 m** | 23.3 – 26.4 mm/s |

The pooled `σ_n = 6.2747e-5` rev/day is the median over 61,861 LEO objects;
these eleven are tracked far better than that, so their own `σ_n` comes back
at 1.3–5.0 × 10⁻⁷ rev/day — **130 to 470 times smaller** — and the shipped
threshold is set entirely by a population floor that has nothing to do with
the object under test. When the per-object noise is used, the binding term
becomes the registration's own 50 m semi-major-axis floor.

### 3.2 Recall

Association on MAD-LEO's own event window (event −6 h / +24 h). 1,134 labels,
**0 not evaluable** — this archive brackets every one of them.

| Arm | window | recall | Wilson 95% | placebo | lift |
|---|---|---|---|---:|---:|
| **pooled (shipped)** | **MAD-LEO event window** | **90/1134 = 7.94%** | **[6.50, 9.66]** | 0.30% | **26.2×** |
| pooled | ±1 d | 105/1134 = 9.26% | [7.71, 11.09] | 0.43% | 21.5× |
| pooled | ±3 d | 155/1127 = 13.75% | [11.87, 15.89] | 1.05% | 13.1× |
| pooled | spacing-aware | 79/1134 = 6.97% | [5.63, 8.60] | 0.30% | 23.2× |
| per-object | MAD-LEO event window | 128/1134 = 11.29% | [9.57, 13.26] | 0.48% | 23.5× |
| per-object | ±1 d | 144/1134 = 12.70% | [10.89, 14.76] | 0.80% | 15.9× |
| per-object | ±3 d | 219/1127 = 19.43% | [17.23, 21.84] | 2.20% | 8.8× |

The **placebo** column is a post-registration control, labelled as such: the
identical association rule applied to the same windows displaced by ±30, ±60
and ±90 days (5,610 placebo windows, those landing within 2 days of another
label discarded). Without it a recall of 7.94% could be nothing but the
background density of flags on objects that are flagged often; it is not —
a flag is **26 times** more likely inside a labelled manoeuvre window than
beside one.

**The plane channel recalled zero of 1,134 manoeuvres**, at both arms. T8b
found its threshold sitting at 3.5° and reported that plane manoeuvres are
essentially unobserved; this is the same fact measured against labels.

### 3.3 Split at the floor — the result that explains the number

| Arm | above the arm's own floor | below it |
|---|---|---|
| **pooled (shipped)** | **81/157 = 51.6%** [43.8, 59.3] | **9/977 = 0.9%** [0.5, 1.7] |
| per-object | 108/216 = 50.0% [43.4, 56.6] | 20/918 = 2.2% [1.4, 3.3] |

**86% of these operators' manoeuvres are below what the shipped detector can
see.** Of what it can see, it catches about half. By burn size (archive-
bracketed |Δa|, a TLE-derived proxy and never evidence):

| |Δa| bin | labels | pooled recall | per-object recall |
|---|---:|---:|---:|
| < 20 m | 576 | 1.0% | 1.4% |
| 20–50 m | 342 | 0.6% | 3.5% |
| 50–100 m | 53 | 1.9% | **39.6%** |
| 100–200 m | 27 | 37.0% | 51.9% |
| 200–500 m | 36 | 58.3% | 61.1% |
| ≥ 500 m | 100 | 50.0% | 51.0% |

The 50–100 m row is the floor moving: 1.9% under the shipped 102–126 m
threshold, 39.6% once the threshold drops to 50 m. Recall does **not** keep
climbing above 200 m — it plateaus near half — which says the remaining misses
are not a sensitivity problem.

### 3.4 By spacecraft, tier and impulse count (shipped arm)

| spacecraft | recall | | tier | recall | | impulses | recall |
|---|---|---|---|---|---|---|---|
| jason-3 | 17/85 = 20.0% | | A (TLE+orbit+SLR) | 44/754 = 5.8% | | 1 | 43/864 = 5.0% |
| jason-2 | 16/111 = 14.4% | | B (TLE+orbit) | 12/194 = 6.2% | | 2 | 41/211 = 19.4% |
| swot | 11/86 = 12.8% | | C (incomplete) | 34/186 = **18.3%** | | 3 | 2/14 = 14.3% |
| sentinel-6a | 4/32 = 12.5% | | | | | 0 (no impulse epoch) | 4/45 = 8.9% |
| saral | 8/67 = 11.9% | | | | | | |
| topex-poseidon | 4/43 = 9.3% | | | | | | |
| jason-1 | 7/119 = 5.9% | | | | | | |
| sentinel-3b | 8/145 = 5.5% | | | | | | |
| cryosat-2 | 13/241 = 5.4% | | | | | | |
| sentinel-3a | 2/147 = **1.4%** | | | | | | |
| hy-2a | **0/58 = 0.0%** | | | | | | |

Tier C — the **least** evidenced labels — has the highest recall, 3× tier A.
That is not a paradox about evidence quality: `confidence_tier` records which
of the three evidence products were present, and the tiers are eras as much as
they are quality. It is reported because the registration required the split,
and it is not interpreted further.

**The per-spacecraft recall is the per-spacecraft burn size, measured.** The
archive-bracketed |Δa| of each spacecraft's own labels, against the shipped
arm's floor:

| spacecraft | median labelled \|Δa\| | labels below the shipped floor | recall |
|---|---:|---:|---:|
| hy-2a | 9.7 m | **58 of 58** | 0.0% |
| sentinel-3a | 22.5 m | **145 of 147** | 1.4% |
| sentinel-3b | 26.6 m | 131 of 145 | 5.5% |
| cryosat-2 | 25.9 m | 218 of 241 | 5.4% |
| jason-1 | 1.8 m | 104 of 119 | 5.9% |
| topex-poseidon | 3.9 m | 35 of 43 | 9.3% |
| saral | 45.2 m | 49 of 67 | 11.9% |
| sentinel-6a | 10.6 m | 21 of 32 | 12.5% |
| swot | 24.8 m | 63 of 86 | 12.8% |
| jason-2 | 7.3 m | 93 of 111 | 14.4% |
| jason-3 | 12.7 m | 60 of 85 | 20.0% |

HY-2A's 0.0% is not a detector that failed on HY-2A: **not one** of its 58
labelled manoeuvres moves the semi-major axis as far as the shipped threshold
requires. Sentinel-3A is the same story at 145 of 147.

### 3.5 False flags, on the same windows

| | shipped arm | per-object arm |
|---|---:|---:|
| labelled-quiet windows | 1,139 (1,423.8 window-days) | same |
| **flags inside them** | **18** | **18** |
| …of which are in windows the dataset itself marks `suspect_unreported_maneuver` | **9** | 9 |
| windows carrying at least one flag | 10 of 1,139 (0.88%) | 10 |
| flags per stable-window-day | 0.0126 | 0.0126 |
| flags inside the labelled span, total | 460 | 715 |
| **unmatched flags** | **321** | 520 |

The 18 is an **upper bound on false flags**: MAD-LEO's stable windows are mined
from a TLE archive, not declared quiet by an operator, and the dataset flags
half of these very windows as suspected unreported manoeuvres. The 321
unmatched flags are reported as a count and are **not** called a false-alarm
rate: the completeness of the published manoeuvre history is not something
this measurement verified.

### 3.6 Campaign-level recall — what the alarm lane would actually have said

The alarm lane does not speak per flag. It speaks at a **campaign start**: a
flag chain with no internal gap longer than 180 days. Over these eleven
spacecraft the whole archive contains **33 campaign starts** (shipped arm)
against 1,134 manoeuvres, so the lane's structural ceiling is 2.9%, and the
measured campaign-level recall is **15/1134 = 1.32%** (per-object arm:
23/1134 = 2.03%). A spacecraft that manoeuvres every fortnight for a decade is
**one campaign**. Neither number may be printed without the other.

### 3.7 The labelled set still agrees with its upstream source

| | labels | matched in the live IDS file (±2 h) | live events after the label span |
|---|---:|---:|---:|
| Sentinel-3A | 147 | **147** | 4 (latest 2026-09-11) |
| Sentinel-3B | 145 | **145** | 3 (latest 2026-08-26) |

Corroboration only, as registered. No headline is computed from it.

---

## 4. Gates

| Gate | Verdict |
|---|---|
| A1 truth-sample offset | did not fire — 0 of 6,272 comparisons dropped |
| A2 row counts | did not fire — every row n ≥ 256 |
| A3 frame residual | did not fire — derived residual ≤ 0.1 m against a smallest reported quantile of 15 m |
| **A4 zero-horizon floor** | **FIRED** — see §2.6 and the deviation in §5 |
| B1 label evaluability | 0 of 1,134 not evaluable on the primary window; 7 on ±3 d |
| **B2 floor printed** | discharged — §3.1 precedes every recall cell |
| **B3 detector untouched** | discharged — `git diff` over `proximity_plane.py`, `trigger_alarm.py`, `alarm_lane_leo.py` empty; blob hashes recorded in the results JSON |
| B4 false-flag count present | discharged — §3.5 |

---

## 5. Deviations from the registration

1. **Gate A4's consequence was applied to one row, not the whole table**
   (§2.6). The registered text said the whole table becomes a floor
   measurement; the diagnostic shows the +0 d residual is a property of the
   element sets and not of the instrument, and the +90 d median is 1,450×
   above it. The fire is reported, the floor is printed beside every row, and
   the +1 d row is labelled floor-limited. A stricter reader may discard the
   +1 d row; nothing else in §2 depends on it.
2. **A placebo control was added** to measurement (B) after registration
   (§3.2), labelled as post-registration. Without it there was no way to say
   whether a single-digit recall beat the background flag density.
3. **A signed along-track quantile was added** to (A), post-registration
   (§2.6), because gate A4 cannot be read without knowing whether the +0 d
   residual is a bias or scatter.
4. **A post-registration outlier rule** was reported beside the registered
   20 m truth screen (§2.5) after the registered screen returned nothing
   usable. Both are reported; neither is used.
5. The manoeuvre-free arm uses the **live IDS histories** (registration §3.7's
   role for them) rather than the MAD-LEO copy; §3.7 shows the two agree on
   every one of the 292 Sentinel-3 labels.

Nothing else departed from the registration, and the registration file was not
edited after it was committed.

---

## 6. What these numbers may not be used for

- **They are not a census.** Eleven cooperative spacecraft with GNSS/DORIS/SLR
  and published manoeuvre logs, and three of them for (A). Precisely what
  makes them measurable — large, well tracked, small frequent planned burns —
  makes them unrepresentative. The (A) numbers are best-case: these are among
  the best-tracked objects in LEO.
- **The recall number is not "the detector's recall"** without the qualifier
  *on this labelled set, these eleven spacecraft, these burn sizes*.
- **Recall does not revise any published precision figure.** T8b's 44.1% and
  the alarm lane's 0.507% were measured on different populations with
  different denominators; precision and recall here do not compose.
- **Nothing here says anything about Starlink**, about constellations, or
  about any operator whose manoeuvre log is not public.
- **No horizon is extrapolated.** Beyond +90 d nothing is measured, and the
  manoeuvre-free arm stops at +14 d.
- Every threshold above — 5σ, the 50 m and 0.01° floors, Γ = 5° and 0.2085°,
  the 20 m screen, the burn-size bins — is a **chosen screen**, not a physical
  law.

---

## 7. Method notes that carry the numbers

- **Propagator**: `satellite.js`, the SGP4 the site's globe runs on, driven
  through `json2satrec` from the archive's own de-quantised elements.
- **Frame chain**: TEME → PEF by GMST evaluated at **UT1** → ITRF by polar
  motion, both from IERS `finals2000A.all`. Neglecting UT1−UTC would rotate
  the Earth by up to |ΔUT1|×15.041 ″/s — ≲ 0.75″ ≈ 26 m at 2023's values and
  13.5″ ≈ 470 m at the treaty limit; neglecting polar motion is ≤ 0.3″ ≈ 10 m.
  What is left is the kinematic equation-of-equinoxes term the GMST rotation
  omits, ≤ 0.003″ ≈ **0.1 m**. All three are `r·θ`, derived, not quoted.
- **No truth interpolation**: the comparison instant is the truth product's own
  nearest sample and SGP4 is evaluated exactly there (offset ≤ 5 s / ≤ 30 s,
  gate A1).
- **Time systems**: EOF tags are UTC; SP3 tags are TAI and converted with
  TAI − UTC = 37 s for 2023. A wrong leap-second count would put every
  Sentinel-3 comparison ~280 km out, which the +0 d row of 0.33–0.58 km
  excludes; a test asserts the conversion directly.
- **Reproduction**:
  `python3 tools/truthset_fetch.py --what {s1,s3a,s3b,ids,madleo,eop}`,
  then `tools/truthset_growth.py` and `tools/truthset_recall.py`;
  `python3 -m unittest tests.test_truthset` (26 tests, all pass).

## 8. What this changes for the programme

1. **M2 (kinematic design §9) is measured for three spacecraft and no more.**
   There is now a measured LEO forward-error curve, per object, against truth:
   LEO member intervals may be drawn for objects whose tracking resembles
   these three, labelled best-case, and the +30 d and +90 d quantiles are the
   numbers to draw. For a typical catalogue object nothing is measured yet.
2. **The site's LEO ribbon needs redrawing** (§2.4): linear in time where the
   error is quadratic, 4–9× too wide at +1 d and 3.3× too narrow at +90 d.
3. **The LEO detector's blindness now has a number, not an adjective.** The
   floor is 102–126 m of semi-major axis (54–59 mm/s) at shipped settings, and
   86% of real manoeuvres on these spacecraft fall below it. Switching to a
   per-object noise floor — the detector's own `object_sigma_contributions`,
   already in the code — moves the floor to the registered 50 m term and takes
   recall from 7.94% to 11.29%, with **no change** in the labelled-quiet
   false-flag count (18 in both arms). That is a measured, cheap improvement
   and a candidate for its own registration.
4. **Paper B's "recall is unmeasured" sentence can be replaced** — by a
   measured number with its interval, its floor, its placebo control, its
   false-flag count and the sentence that it is a benchmark on eleven
   spacecraft and not a census.
5. **The alarm lane's campaign chaining costs it almost all of the recall it
   has** (§3.6): 1.32% at campaign level against 7.94% at flag level, with a
   structural ceiling of 2.9% on this population.
