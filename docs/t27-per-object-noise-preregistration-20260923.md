# T27 pre-registration — the per-object-noise detector arm, as a registered change candidate

**Status: REGISTRATION ONLY. Committed alone, before the instrument exists and
before any T27 number is computed.** Nothing in this file may be edited after
it is committed; departures are recorded in the results document as deviations.

**Track:** ORB-T27. **Date:** 2026-09-23. **Host:** `pc`, CPU only, `nice`.
**Production detector:** untouched. This track decides whether a change *should*
ship; it ships nothing.

---

## 0. Why this track exists, and what it is not

Two independent measurements have already flagged the same one-line change as
the cheapest recall improvement the programme has found, and both said in terms
that it is unregistered and owes its own registration:

- **T16b** (`docs/t16b-truthset-results-20260922.md` §8.3), eleven geodetic and
  altimetry spacecraft, 1,134 operator-reported manoeuvres: recall
  **7.94% [6.50, 9.66] → 11.29% [9.57, 13.26]** with the labelled-quiet
  false-flag count **unchanged at 18**.
- **T21** (`docs/t21-differential-results-20260923.md` §5, "OWED" in §11),
  Sentinel-3A/3B, 241 evaluable labels: **8/241 → 19/241** at a false-flag rate
  of 0.019178 against the shipped arm's 0.016438 — **1.167×**.

Neither number was produced by a registration whose subject was the change.
T16b registered a *recall benchmark* and carried the per-object arm as a
diagnostic; T21 registered a *differential detector* and found the per-object
arm beating its own swept arms as a by-product. **A change that reaches
production on the strength of two by-products is a change nobody registered.**
This file registers it.

**What this track is not.** It is not a proposal to ship. It is a registered
measurement whose decision rule (§6) can return NOT SHIPPED, and the clauses
most likely to return that are the ones the two by-products never looked at:
the passive control (E3) and the price the whole catalogue pays (E4).

---

## 1. The change, stated exactly

### 1.1 What is shipped today

`tools/proximity_plane.detect_manoeuvres(el, sigma_n, sigma_theta)` is called
with **pooled, population-wide** scale parameters:

```
POOLED_SIGMA_N     = 6.2747e-5  rev/day     (median of object_sigma_contributions
POOLED_SIGMA_THETA = 0.6994     degrees      over 68,749 catalogue objects, T8b
                                             detect stage; p95 5.3954e-3 and 2.9026)
```

Inside the detector the in-track threshold is, per element set,

```
thr_n = max( BURN_SIGMA_K * sigma_n ,            # 5 sigma, fit-noise term
             3 * |ndot| * spacing ,              # the object's OWN drag term
             1.5 * n * DA_FLOOR_KM / a )         # the registered 50 m floor term
```

and the plane threshold is `thr_p = max(BURN_SIGMA_K * sigma_theta, I_FLOOR_DEG)`
with `BURN_SIGMA_K = 5.0`, `DA_FLOOR_KM = 0.050`, `I_FLOOR_DEG = 0.01`,
`BURN_BASELINE_SAMPLES = 10`, `CAMPAIGN_MAX_GAP_DAYS = 180.0`.

### 1.2 What the change switches, and *only* that

The change replaces the two pooled scalars with the object's own values, from
the estimator **already in the production file**:

```
sigma_theta, sigma_n = proximity_plane.object_sigma_contributions(el)
```

**Nothing else changes.** Not `BURN_SIGMA_K`, not `DA_FLOOR_KM`, not
`I_FLOOR_DEG`, not the drag term, not the two-consecutive-sets-agreeing-in-sign
confirmation rule, not the campaign chaining, not the flag epoch convention.
The change is exactly two arguments at one call site.

### 1.3 The estimator, as the code actually computes it

`object_sigma_contributions(el)`:

- `theta_step[i] = plane_separation_deg(inc[i+1], raan[i+1], inc[i], raan[i])`;
  `sigma_theta = mad_sigma(second_difference(theta_step), sqrt(6))`.
- `sigma_n = mad_sigma(second_difference(n), sqrt(6))`.
- `mad_sigma(x, f) = median(|x - median(x)|) * 1.4826 / f`.
- Returns `(nan, nan)` when the object carries fewer than 8 element sets.

**Window: the object's entire retained history.** The estimator's own docstring
says the statistic is "taken inside the object's own quiet stretches"; the code
performs **no quiet-stretch selection**. Robustness to manoeuvres comes from the
median absolute deviation, which is unmoved by a minority of large steps, and
from the second difference, which annihilates any smooth secular rotation and
the drag trend. This registration binds the **code's** behaviour, not the
docstring's, and the results document must say so where it reports σ.

The `sqrt(6)` divisor is derived, not chosen: for independent errors of scale σ
the second difference `y[i+2] - 2y[i+1] + y[i]` has variance
`(1 + 4 + 1) σ² = 6 σ²`, so dividing the robust scale of the second difference
by `sqrt(6)` returns σ. This is an assumption about the *error model*, not a
physical law: it is exact only for independent, identically scaled fit errors,
and it is stated here as the screen it is.

### 1.4 The registered fallback ladder

A catalogue-wide arm needs a defined answer for every object. T16b's instrument
simply skipped objects whose σ came back non-finite; that is not available to a
change that would run on the whole catalogue. Registered, in order:

1. `detect_manoeuvres` already returns **no flags** for an object with fewer
   than `BURN_BASELINE_SAMPLES + 3 = 13` element sets. Unchanged by this track.
2. If `object_sigma_contributions` returns a **non-finite** value in a channel
   (fewer than 8 element sets, or an all-NaN difference series), that channel
   falls back to **the pooled value for that channel alone**. The other channel
   keeps its per-object value. Every fallback is counted and reported.
3. If a channel's per-object σ is **exactly zero** (a possible MAD outcome on a
   heavily quantised or short series), it is **not** replaced. Zero σ makes the
   50 m / 0.01° floor terms binding, which is the designed behaviour of the
   threshold expression, and the count of such objects is reported.
4. No clipping, no shrinkage toward the pooled value, no winsorising. Any of
   those would be a second, unregistered change.

### 1.5 A prediction this registration is obliged to make first

T16b §3.1 already measured that on all eleven label spacecraft the per-object
`sigma_n` comes back at 1.3–5.0 × 10⁻⁷ rev/day — 130 to 470 times below the
pooled 6.2747e-5 — so on every one of them `5 σ_n` stops being the binding term
and **the 50 m `DA_FLOOR_KM` term binds instead**.

The arithmetic consequence, derived before any T27 number: on the eleven-
spacecraft label set, *the per-object arm's threshold does not depend on the
per-object σ at all*. It depends only on the 50 m floor and the object's own
drag term. **Therefore the honest description of the measured T16b gain may be
"the 50 m floor became binding", not "the detector adapted to the object".**

This is a falsifiable prediction with a registered consequence:

> **If placebo arm P1 (§5.1) reproduces the per-object arm's recall on the
> eleven spacecraft to within one label, the results document must describe the
> change as *lowering the floor to 50 m on well-tracked objects* and must not
> describe it as per-object adaptation.** The word "adaptive" is then withheld
> from the whole document.

Where per-object σ *does* matter is the other direction — objects whose own σ
is **larger** than pooled, which raises their threshold and should remove their
flags. The catalogue contains many: T8b measured the population p95 at
5.3954e-3 rev/day, **86× the pooled median**. Those objects are debris and
badly-tracked fragments, i.e. exactly the passive control population of E3.
**The change is therefore predicted to cut both ways, and E3 is where that is
measured.**

---

## 2. Populations, labels and exposure

| Set | Definition | Size |
|---|---|---|
| **L** — the label set | MAD-LEO mission-reported annotations (CC BY 4.0, doi 10.6084/m9.figshare.33446503.v1), eleven geodetic/altimetry spacecraft | 1,134 manoeuvres |
| **Q** — labelled quiet | MAD-LEO stable windows for the same eleven | 1,139 windows, 1,423.75 window-days |
| **C** — the LEO catalogue | every object in the programme's own archive whose regime is LEO, from the T13 element-set column cache (`/home/sdegan/t13-work`, 68,749 objects, 217,046,214 rows) | 61,734 LEO objects, 112,842,668 object-days |
| **P** — catalogue-passive | `object_type` ∈ {DEBRIS, ROCKET BODY} within **C**, admitted at `CONTROL_MIN_ELEMENT_SETS = 200` and `CONTROL_MIN_SPAN_DAYS = 365` | measured, reported |
| **Y** — payload | `object_type = PAYLOAD` within **C**, same admission | measured, reported |
| **N** — never-manoeuvred, frozen | the T8b class as the **shipped** detector defined it: no in-track and no plane flag, ≥ 200 element sets, ≥ 365 days span | 3,011 objects (855 of them payload-class) |

**C, P and Y are read from the existing T13 cache and the archive, read-only. No
large artefact is written by this track.** Disk is reported before and after.

**The eleven-spacecraft numbers do not compose with the catalogue-wide numbers**
and are never used as each other's baseline (T21 §7's rule, inherited here). E1,
E2 and E5 live on **L/Q**; E3 and E4 live on **C/P/Y/N**; no increment crosses
the two.

---

## 3. Estimands

### E1 — recall at the shipped false-flag operating point

**Primary cell.** Recall over the full **L** (1,134 labels, eleven spacecraft),
association on MAD-LEO's own event window (event −6 h / +24 h), for three arms:
**shipped** (pooled σ), **per-object** (the change), and the two placebos of §5.

Reported with **Wilson 95%** intervals, and:

- **per burn-size bin** on the archive-bracketed `|Δa|` proxy, registered bins
  `<20, 20–50, 50–100, 100–200, 200–500, ≥500 m` — *a stratifier, never
  evidence*, because it is read from the very elements the detector reads;
- **the increment** (per-object − shipped) in percentage points, with **two**
  bootstrap intervals, both registered before any number:
  - **object-cluster bootstrap**: resample the eleven spacecraft with
    replacement, 2,000 draws, seed **20260923**;
  - **90-day time-block bootstrap**: partition the label span into contiguous
    90-day blocks, resample blocks with replacement, 2,000 draws, same seed;
  - the **arm of record for the decision rule is the more conservative of the
    two lower bounds**, named before the measurement so the choice cannot be
    made after seeing it;
- **the increment against the cadence-only schedule floor**, T18's 5.115%
  [3.977, 6.555] measured at this same operating point on this same label set,
  printed beside the shipped 7.937%;
- **the minimum detectable effect (MDE)**: the half-width of each bootstrap
  interval, stated as "the smallest increment this design could have
  demonstrated in either direction". An increment inside the MDE is reported as
  **not demonstrable by this design**, never as a trend (T18 §2.2's reading,
  inherited).

**Operating point.** T16b measured both arms at **the same labelled-quiet
false-flag count, 18**, which is what makes the comparison a comparison. T27
reports the achieved quiet-flag count for every arm beside its recall and, if
the two arms do not land on the same count, reports the per-object arm's recall
at its own count and states the mismatch in the increment's caption rather than
silently comparing across operating points.

**A placebo association control** (T16b §3.2's, post-registration there, fully
registered here): the identical association rule applied to the same windows
displaced by ±30, ±60, ±90 days, discarding placebo windows landing within
2 days of another label. Reported for every arm, as recall and as lift.

### E2 — the two false-flag counts, as counts

For each arm, over **Q**:

1. **flags inside labelled-quiet windows** — an *upper bound*, because MAD-LEO's
   stable windows are mined from a TLE archive rather than declared quiet by an
   operator, and the dataset itself marks some of them
   `suspect_unreported_maneuver`. The suspect-marked subset is reported
   separately, as T16b does.
2. **unmatched flags** — flags anywhere inside the label span not matched to any
   label. Reported as a **count** and never as a false-alarm rate: the
   completeness of the published manoeuvre history is not verified here.

Also reported: flags per stable-window-day, and windows carrying ≥ 1 flag.
T16b's published values (18 / 18 and 321 / 520) are what gate **G2**
must reproduce.

### E3 — the passive control (the Paper B apparatus)

This is the clause the two by-product measurements never ran, and it is the one
this registration exists for.

**E3a — the physically-defined passive class. GATING.** Over **P** (DEBRIS and
ROCKET BODY in LEO), for both arms: flags, exposure in object-days, **flags per
object-day** and per object-year, with **Jeffreys 95%** intervals, and the
fraction of passive objects carrying any flag. Paper B's convention is kept:
the passive rate is read at its **upper** bound and the payload rate at its
**lower** bound whenever the two are compared, and a zero count receives a
non-zero upper bound — *a zero point estimate is never reported as a zero
bound*. The class is an **upper bound** on the false-alarm rate, because some
rocket bodies do perform disposal burns, and it is labelled as such everywhere.

> **The registered bar.** The change **fails E3a** if the per-object arm's
> Jeffreys 95% **lower** bound on the passive flag rate exceeds the shipped
> arm's Jeffreys 95% **upper** bound — i.e. if the increase in the passive rate
> is *demonstrated* rather than merely observed. The point-estimate ratio is
> reported beside it in every case.

**E3b — the frozen never-manoeuvred class. REPORTED, NOT GATING, and the reason
is circularity.** **N** is *defined* by carrying no flag under the shipped
detector, so the shipped arm's rate on it is **zero by construction** and any
per-object flag makes the change look worse for a reason that is not about the
change. The production file says exactly this at
`proximity_plane.detector_false_alarm_rate` ("that class is DEFINED by having no
flag … the same tautology prereg 4.7 warns about"). Registered treatment:

- the class membership is **frozen at the shipped detector's definition** and
  re-scored under the change over the same objects and the same exposure;
- reported as **events / object-days with Jeffreys intervals**, with the
  circularity named in the same sentence, every time;
- a **secondary screen, not a ship-blocker**: if more than **10%** of the frozen
  855 never-manoeuvred *payload* objects acquire a flag under the change, that
  is recorded as a named concern in the results and in the runbook row.

**Declared scope limit, registered rather than discovered.** T8b's published
control figure — **zero events over 18,792,698 object-days** — is an
*approach-event* rate over 855 dead payloads produced by T8b's whole analyze
stage (pair screening, geometry arms, nulls), not a flag rate. Re-deriving it
under a changed detector means re-running that stage, which is outside this
track's compute. **T27 re-scores the control at flag level and carries T8b's
approach-event figure as context only.** This is a deviation from the conductor's
brief, it is registered here in advance rather than reported afterwards, and the
results document and the report must both name it as unproven in those words.

**E3c — the alarm lane's own passive ratio.** `docs/alarm-lane-build-20260922.md`
§7.2 records that the live LEO arm **fails its passive control at 0.797** of the
per-object rate it raises on objects that can manoeuvre, against a design bar
of 0.001, and that this is what withholds its published clause. A detector
change must not make that worse. Registered: campaign-initiating in-track alerts
per object-year on **P** divided by the same on **Y**, both arms, over **C**.

> **The registered bar.** The change **fails E3c** if that ratio is larger under
> the per-object arm than under the shipped arm.

### E4 — the catalogue-wide price

The alarm lane inherits every flag the detector raises, so a change owes the
number of extra flags the whole LEO catalogue produces. Over **C**, both arms:

- total in-track flags, total plane flags, flags per object-year;
- **campaign starts** (chains with no internal gap > 180 days) — what the alarm
  lane actually consumes — total and per year, using the archive's own span;
- objects carrying at least one flag;
- the same, split payload / catalogue-passive;
- the fallback counts of §1.4 and the count of objects whose per-object σ
  **exceeds** the pooled value (the direction that removes flags) against those
  below it.

> **The registered bar.** The change **fails E4** if either the catalogue-wide
> flags per object-year **or** the campaign-start count under the per-object arm
> exceeds **2.0×** the shipped arm's.

**This clause is declared weak, in advance.** The eleven-spacecraft flag ratios
are already published — 460 → 715 in-span (1.55×) and 321 → 520 unmatched
(1.62×) — so 2.0 is a round bound chosen *above a ratio already known*, not a
threshold derived from anything. It can only fail loudly. It is a guard against
a blow-up on the badly-tracked majority of the catalogue, which nobody has
measured, and it is **not** a discriminating test. The discriminating clauses are
E1 and E3.

### E5 — the 50–100 m bin, and the reversal clause

T18 §2.3 registered a reversal clause and it fired; T16b's own bin table shows
the 50–100 m bin moving 1.9% → 39.6%, which is the floor moving and nothing
else. Registered here:

- the **50–100 m bin** is reported with Wilson intervals for every arm, first,
  before the pooled claim;
- **the reversal clause, inherited verbatim in shape**: if **any** burn-size bin
  has the per-object arm *worse* than the shipped arm with a bootstrap interval
  excluding zero, **the pooled E1 claim is WITHHELD and the reversal is the
  result**;
- the **per-bin location of the increment** is printed against the schedule
  floor, because T18's finding was that its increment lived entirely below the
  detector floor where hits are barely separable from the model's own
  background. **T27's per-bin table must show where THIS increment lives**, and
  the results document must state in one sentence whether it lives above or
  below the shipped arm's 102–126 m floor.

---

## 4. Decision rule

**SHIP-CANDIDATE** if and only if **all** of:

1. **E1** — the increment's lower bound is **> 0** on the arm of record (the
   more conservative of the object-cluster and 90-day-block bootstraps), and the
   increment is **not inside the MDE**;
2. **E3a** — the passive rate is **not worse** by the bound-versus-bound test of
   §3 E3a;
3. **E3c** — the alarm lane's passive/payload alert ratio is **not larger**;
4. **E4** — catalogue-wide flag and campaign growth is **within 2.0×**;
5. **E5** — no burn-size bin reverses with an interval excluding zero.

**Otherwise NOT SHIPPED, and the results document names the failing clause in
its first paragraph.** A SHIP-CANDIDATE verdict is a recommendation to the
operator and nothing more: this track does not edit the production detector, the
alarm lane, the site, or any published number, whatever it measures.

**A clause that cannot be evaluated is a failing clause.** "Unmeasured" is not
"passed".

---

## 5. Placebo arms

### 5.1 P1 — donor-permuted σ (ARM OF RECORD for the placebo question)

Each object receives **another object's** per-object σ, drawn as a random
derangement of the arm's own σ values with seed **20260923**, matched on
nothing. The question P1 answers is the only one that matters for describing the
change honestly: **is the gain "the right threshold for this object", or merely
"a smaller number"?**

Registered readings, fixed now:

- P1 recall **indistinguishable** from the per-object arm ⇒ the gain is not
  per-object adaptation; §1.5's consequence applies and the change is described
  as lowering the floor.
- P1 recall **materially below** the per-object arm ⇒ the per-object σ is doing
  real work, and the change may be described as adaptive.

### 5.2 P2 — time-shifted-window σ (as the conductor's brief names it)

For each object, σ is computed from the object's own element sets restricted to
a window displaced by **−730 days** from the span used for detection (falling
back to **+730 days**, then to the whole history, when the displaced window
holds fewer than 8 sets; every fallback counted). Reported for E1 and E2.

**P2 is expected to reproduce the per-object arm closely**, because a whole-
history robust scale is stable in time, and that expectation is written down
*here* so that a close reproduction is not later presented as a passed placebo.
P2's informative failure mode is the opposite one: a displaced-window σ that
differs materially would mean the estimator is unstable, which would be a
finding about the estimator.

### 5.3 The association placebo

The ±30/±60/±90-day displaced-window association control of §3 E1 is carried for
every arm including both placebos.

---

## 6. Gates

| Gate | Clause | Consequence if it fires |
|---|---|---|
| **G1** | **The production detector is untouched.** `git diff` over `tools/proximity_plane.py`, `tools/trigger_alarm.py`, `tools/alarm_lane_leo.py`, `pipeline/orbit_events.py` must be empty at measurement time, and the blob hash of each is recorded in the results JSON. | The whole track is void. |
| **G2** | **Reproduction before novelty.** Before any new T27 number is read, the instrument must reproduce T16b's published cells **exactly**: shipped 90/1,134 with 18 quiet flags and 321 unmatched; per-object 128/1,134 with 18 and 520. | No T27 number may be reported; the discrepancy is the result. |
| **G3** | **No cross-population increment.** No number computed on the eleven spacecraft is differenced against a number computed on the catalogue, in either direction. | The offending cell is deleted, not caveated. |
| **G4** | **MDE beside every increment.** An increment whose magnitude is below its own interval half-width is reported as not demonstrable by this design. | Reported as such; it may not be read as a trend. |
| **G5** | **The `\|Δa\|` proxy is a stratifier and never evidence**, because it is read from the same elements the detector reads. No claim rests on it. | The claim is withdrawn. |
| **G6** | **No physical claim without a derivation or a citation.** Every threshold named here is a screen, not a law, and the results document says so where it names one. | The claim is withdrawn. |
| **G7** | **Exposure floor for E3a.** If **P** admits fewer than 200 objects or the Jeffreys interval on either arm's passive rate is wider than the difference it is asked to resolve, E3a is reported **UNDERPOWERED** and, per §4, **counts as a failing clause**. | NOT SHIPPED, clause E3a. |

---

## 7. What this track may not be used for

- **Not a census.** The eleven label spacecraft are large, cooperative, well
  tracked, and manoeuvre often in small planned steps. Precisely what makes them
  measurable makes them unrepresentative. No recall number here is about
  Starlink, about any constellation, or about any operator whose manoeuvre log
  is not public.
- **Not a revision of any published precision figure.** T8b's 44.1% and the
  alarm lane's 0.507% were measured on different populations with different
  denominators. Recall and precision here do not compose.
- **Not an authorisation.** A SHIP-CANDIDATE verdict authorises nothing; the
  production detector, the frozen alarm-lane tables and every published number
  stay exactly as they are until the operator rules.
- **Not a statement about the plane channel.** T16b measured the plane channel
  recalling **zero** of 1,134 manoeuvres at both arms. If it does so again, that
  is reported and nothing is concluded from it beyond what T8b already published.

---

## 8. Reproduction

```
python3 tools/per_object_noise.py --out docs/t27-per-object-noise-20260923.json
python3 -m unittest tests.test_per_object_noise
```

Inputs, all read-only: the programme archive
`/home/sdegan/space-orbit-history/orbit-history.sqlite3`; the MAD-LEO tables and
manifests under `/home/sdegan/t16b-truth`; the T13 element-set column cache
under `/home/sdegan/t13-work`; T8b's frozen detect artefacts under
`/home/sdegan/t8b-work`. **No large artefact is written.** The only outputs are
the results JSON and the results Markdown, both in `docs/`.

Seed **20260923** everywhere. CPU only on `pc`; no GPU stage is declared and
none may be used.
