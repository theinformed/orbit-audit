# T4 — Constellation manoeuvre synchrony: DESIGN AND DRAFT REGISTRATION

> **STATUS: DRAFT / DESIGN ONLY. NOTHING HERE IS REGISTERED AND NOTHING HERE
> IS IMPLEMENTED.** This document is the runbook's T4 deliverable
> ("design + pre-registration draft only",
> `docs/research-program-runbook-20260921.md`). It may be freely revised. The
> day T4 is actually run, a **separate** `docs/synchrony-preregistration-<date>.md`
> is committed **alone and ahead of every T4 number**, in the manner of
> `docs/phase3-preregistration-20260921.md` and
> `docs/cadence-preregistration-20260921.md`. Nothing in this draft licenses a
> synchrony claim, and §7 below is a skeleton of that future registration, not
> the registration itself.

Written 2026-09-21 alongside T3's measurement pass. T3's registration is
`docs/cadence-preregistration-20260921.md`; its results are
`docs/cadence-results-20260921.md`. Where this document cites a T3 number it
cites it as an input, and every such citation carries its provenance.

---

## 1. The question, stated so it can be wrong

A constellation operator can keep station in two fundamentally different ways:

- **Fleet-commanded.** A ground segment plans burns for many satellites in one
  operation — a weekly or monthly manoeuvre campaign, a plane-wide phasing
  correction, a fleet-wide response to a drag event. The burns of different
  satellites are then *correlated in time* beyond what their individual orbits
  require.
- **Autonomous / per-satellite.** Each satellite keeps its own box on its own
  schedule, triggered by its own drift against its own deadband. Burns are
  then correlated only through whatever the satellites share physically —
  the same shell, the same atmosphere, the same solar cycle.

**T4's question:** does a given operator's fleet show manoeuvre timing
correlation *in excess of what the shared physical environment already
explains*?

This is a question about operations inferred from public element sets alone,
and the honest framing matters: a positive result says the timing is
*coordinated*, not that we know the command path; a null result says the
coordination is below what our attenuated detector can see, not that it is
absent (§5).

## 2. Why the naive version of this is wrong

The obvious design — take manoeuvre epochs for one operator's satellites,
cross-correlate them, compare against a null in which epochs are scattered
uniformly at random — is wrong in a way that would produce a confident,
publishable, false answer.

**Confound 1: shared drag.** A geomagnetic storm raises thermospheric density
across a whole shell within hours. Every satellite in that shell loses altitude
faster, hits its deadband sooner, and reboosts within days of the others —
with no command, no coordination and no ground segment involvement whatsoever.
Against a uniform-scatter null this is overwhelming apparent synchrony.
Magnitude is not speculative: the drag-driven semi-annual and 27-day density
terms T3's §6.5 catalogues are the same driver acting on a longer timescale,
and storm-driven density excursions are larger still.

**Confound 2: shared launch and shared ageing.** Satellites launched together
are commissioned together, raise orbit together, and reach end of life together.
Their manoeuvre intensity envelopes are similar *in shape and in absolute
time* for reasons that have nothing to do with day-to-day coordination.

**Confound 3: shared tracking.** Two satellites in the same plane are observed
by the same sensors at the same passes. Their element-set epochs are correlated,
so their *detection opportunities* are correlated, so their *detected* epochs
are correlated even if their true epochs are not. T3's §0.2 measured exactly
this structure: the archive's epoch pattern is a comb at integer multiples of
the solar day, shared across objects.

**Confound 4: the detector's own recall is not 1, and is not constant.** §5.

A design that does not answer all four is not worth running.

## 3. The design

### 3.1 Primary estimand: a DIFFERENCE in synchrony, not synchrony

The single most important design decision. The primary quantity is **not**
within-operator synchrony. It is

> **S_diff(A) = synchrony(within operator A) − synchrony(A against a
> shell-matched non-A control set)**,

where the control set is drawn from objects in the same registered
perigee × inclination × eccentricity strata (the Paper B bands T3 already
borrows) and the same era, but belonging to a *different* operator, or to no
operator at all.

Confounds 1, 2 and 3 act on the control set as strongly as on the fleet: the
shell-matched non-A objects fly through the same storms, are tracked by the same
sensors, and are aged by the same atmosphere. What they do not share is A's
ground segment. **The difference is the operational signal; the level is not.**

Two secondary arms, both registered as secondary and never promoted:

- **S_within(A)** against the circular-shift null of §3.3 — reported as
  context, because a fleet and its shell-matched control can both be highly
  synchronous and the difference still zero, and a reader should see that.
- **S_plane(A)** — within-plane against between-plane synchrony inside the same
  operator. Fleet-commanded phasing is usually organised by orbital plane, so a
  plane-structured excess is a *specific* prediction that autonomous keeping
  does not make. This is the most falsifiable arm in the design and is worth
  running even where S_diff is null.

### 3.2 Two channels into synchrony, and why the phase channel comes first

**PRIMARY — the phase channel (no event detection, therefore no recall
penalty).** T3 already fits, per object per 1080-day window, a sinusoid at the
dominant frequency `f*`. That fit has a **phase**, which T3 does not currently
record and which T4 requires. For a set of objects sharing a cadence, the
statistic is the **Rayleigh resultant** of their phases,
`R = |sum_k exp(i * phi_k)| / K`, evaluated only over objects whose `f*` agree
to within the registered grid resolution.

This channel's advantage is structural: it never asks "when was the burn", so
it is not attenuated by the probability of detecting an individual burn. Its
cost is a *selection* rather than an attenuation — it can only speak about
objects in which T3 found a rhythm at all, which is T3's E1 fraction, and that
denominator must be stated on every number.

Two things must be registered carefully here, and both are genuinely open:

1. **A common phase is not the only signature of a commanded fleet.** A
   ground segment that deliberately *staggers* burns across a plane — the
   normal way to avoid simultaneous manoeuvres in a dense shell — produces
   phases that are *uniformly spread*, which is exactly what the null predicts.
   The Rayleigh test would then be blind to the strongest possible form of
   coordination. A registered companion statistic is therefore required: the
   **K-th order resultant** `R_K = |sum exp(i*K*phi_k)|/K_count` for K equal to
   the number of satellites per plane, which is large precisely when phases are
   evenly staggered. Both are reported; neither is chosen after seeing which
   one worked.
2. **Phase is only meaningful relative to a common clock.** All phases must be
   referred to one absolute epoch, not to each object's own window start.

**SECONDARY — the epoch channel (attenuated by recall).** Manoeuvre epochs
from the existing detector in `pipeline/orbit_campaigns.py`. Pairwise
cross-correlogram `C_ij(tau)` counted in registered lag bins, summed over pairs,
compared against the §3.3 null. This is the channel §5's recall bound bites,
and it is the one that would most obviously benefit from T5a's compute.

### 3.3 The null: circular shift, per object, never uniform scatter

For every resample, each object's **entire epoch train (or phase) is shifted by
one random offset**, drawn uniformly over its observation span, with wrap.
This is the standard "trial-shift"/"jitter" family of nulls used for spike-train
synchrony in neuroscience (Grün 2009, *J. Neurophysiol.* 101, 1126, "Data-driven
significance estimation for precise spike correlation"; Fujisawa, Amarasingham,
Harrison & Buzsáki 2008, *Nat. Neurosci.* 11, 823, for the interval-preserving
variant), and it is chosen here for the property that matters:

- it **preserves exactly** each object's own inter-event interval distribution,
  its cadence, its burn count and its activity envelope's *shape*;
- it **destroys** alignment between objects.

A uniform-scatter null preserves none of this and would be significant for
almost every fleet. The circular shift is the weakest null that is not
obviously wrong — and it is still not enough on its own, which is why §3.1's
control-set difference, not the shift null, carries the primary claim. The shift
null supplies the reference distribution for `S_diff`; it is not asked to
absorb the environment.

Registered resample count and seed go in the real registration (§7); the
draft's placeholder is 2,000 shifts, seeded by the registration date, matching
Paper B's and Phase 3's convention.

### 3.4 The space-weather arm, and a hard prerequisite this design has already hit

The cleanest way to show the shared-drag confound has been handled is to
condition on it: stratify or regress the synchrony statistic on geomagnetic
activity (Ap or Kp) and solar flux (F10.7) over each window, and show `S_diff`
survives.

**This archive cannot currently do that.** The `geomagnetic` table of
`orbit-history.sqlite3` holds **25 rows, all `kp`, spanning 1785996840000 to
1786018200000 ms — about six hours of 2026-08-05**
<!-- src: sqlite query over object archive geomagnetic table, 2026-09-21 -->.
Against a design that needs decades of daily indices, that is empty.

So T4 carries a **named prerequisite**: a historical Ap/Kp and F10.7 series
must be ingested (GFZ Potsdam publishes the definitive Kp/Ap series back to
1932; NOAA/Penticton publishes F10.7 back to 1947) before the space-weather arm
can be registered as anything other than "not done". This is written down here,
before T4 exists, so that it cannot later be presented as a limitation
discovered at the end. Until it exists, §3.1's shell-matched control set is the
*only* handle on confound 1, and the registration must say so in those words.

### 3.5 What T3 hands over, concretely

| T3 output | T4 use | Status |
|---|---|---|
| Per-object dominant period `f*` and per-window `f*` | Defines the cadence-matched groups within which phase is compared | **Exists** (`docs/cadence-results-20260921.jsonl`) |
| Per-object / per-window significance verdict | The denominator: which objects the phase channel may speak about at all | **Exists** |
| Per-window sinusoid **phase** at `f*` | The primary statistic itself | **DOES NOT EXIST — T3 computes it inside `gls_power` and discards it.** Recovering it is a small, additive change to `tools/cadence_core.py` (the `YC`, `YS`, `CC`, `SS`, `CS` terms already computed give the fitted amplitude and phase in closed form) and is T4's first implementation task |
| Change-points (shift / stop) | A second synchrony question: do fleet *cadence changes* coincide? A fleet-wide ops or software change is a sharper, rarer, more identifiable event than a burn | **Exists** |
| Matching rung per object | Excludes objects whose T3 verdict rests on a pooled fallback threshold from carrying a T4 claim | **Exists** |
| Passive-audit false-positive rate | Bounds how much of any apparent synchrony could be synchronised *noise* | **Exists** |
| Measured detection recall | §5 — the bound on what T4 can claim | **DOES NOT EXIST anywhere in this programme.** §5.2 |

## 4. Operator and plane assignment — an unglamorous prerequisite

The design needs to know which objects belong to which fleet, and which plane.

- **Fleet**: from the catalogue's `object.name` prefix, as T3's results table
  already does. This is adequate for the large unambiguous families and
  inadequate for everything else; T4 must publish its fleet membership list and
  the objects it could not assign, never a silent "unclassified" bucket.
- **Plane**: derivable from the elements themselves — objects of one plane share
  inclination and share a RAAN that regresses together. `raan` **is archived**
  (`element_set.raan_q`), and T3's extractor does not currently pull it; adding
  it is trivial. Plane assignment is a clustering step and therefore a *fitted*
  quantity, so the registration must fix its algorithm and its tolerance in
  advance, or it becomes a free parameter that can be tuned until `S_plane`
  works.

## 5. The recall bound — how much T4 is allowed to claim

### 5.1 The arithmetic, derived

Let `r` be the probability that a genuine manoeuvre produces a detected epoch.
For a pair of satellites that truly burn together, **both** burns must be
detected for the pair to contribute a coincidence, so the observed excess
coincidence rate is attenuated by `r^2`. With three-way and higher-order
coincidences the attenuation is `r^k`.

The consequences are severe and must be stated as bounds, not caveats:

- At `r = 0.5`, three quarters of true pairwise coincidences are invisible.
- At `r = 0.3`, 91% are.
- A **null** epoch-channel result at `r = 0.3` is consistent with a fleet in
  which every single burn is commanded together. Such a result must be reported
  as **"below our detection floor"**, and the registration must fix, in advance,
  the smallest true synchrony fraction the run could have detected at 80% power
  given the measured `r` — the **minimum detectable synchrony**, computed and
  published *before* the numbers, exactly as an acceptance criterion.
- `r` is **not constant across objects**: it rises with burn size and with
  tracking cadence, and both vary across a fleet and between a fleet and its
  control set. A control set with systematically *lower* `r` than the fleet
  would manufacture a positive `S_diff` out of nothing. The registration must
  therefore either match the control set on the covariates that drive `r`
  (burn-size proxy and epoch cadence — the latter is already a T3 stratum
  factor) or measure `r` per stratum and correct, and must say which.

The phase channel (§3.2) is exempt from the `r^2` attenuation but not from
selection: it speaks only about objects T3 called rhythmic.

### 5.2 Recall is not measured anywhere in this programme, and T4 must measure it

Paper B and Phase 3 measure the **false alarm** side exhaustively and the
**recall** side not at all; the runbook's T5a names detection recall as *the*
measured bottleneck. So T4 cannot inherit an `r`; it has to produce one.

The design's proposal — cheap, free of new data, and using the same negative
control the rest of the programme already relies on:

> **Injection–recovery on passive objects.** Take real passive-class element
> histories, which by construction contain no manoeuvres. Inject synthetic
> step changes in mean motion of known size and known epoch, drawn from a
> registered grid of amplitudes spanning the physically interesting range.
> Run the unmodified detector. `r(amplitude, cadence, regime)` is the recovered
> fraction.

Its virtues: the substrate is real (real sampling pattern, real fit noise, real
gaps), the ground truth is exact, the control class costs nothing, and the
result is a recall *surface* over the covariates that matter rather than a
single number. Its declared limitation, which must be registered rather than
discovered: an injected instantaneous step is not a real burn — a real
manoeuvre is followed by a re-fit transient and sometimes by a corrective burn
— so the measured `r` is an **upper bound** on true recall, and the synchrony
bound derived from it is correspondingly optimistic. Saying that in advance is
the difference between a bound and a boast.

## 6. What would make T4 worth running, and what would make it not

Stated now, while it is still cheap to decide not to do this.

**Worth running if**, from T3's measured results:
- at least one operator family has **>= 30 objects** with a significant T3
  rhythm, so a within-fleet statistic has a denominator; **and**
- a shell-matched non-fleet control set of comparable size exists in the same
  strata, so §3.1's difference is computable; **and**
- T3's Gate A came out CALIBRATED, because a synchrony statistic built on
  detections whose false-positive rate is unknown measures the synchrony of the
  noise.

**Not worth running if** T3's rhythmic fraction is concentrated in one or two
operators with no shell-matched control, or if Gate A failed. In that case the
honest next step is the recall measurement of §5.2 on its own, which is
independently valuable to Paper A and to the T5a proposal, and T4 waits.

## 7. Skeleton of the registration that would be committed before any T4 number

Each heading below is a decision that must be fixed in writing, alone, ahead of
every T4 result. Where this draft already has a position it is noted; where it
does not, the gap is named rather than papered over.

1. **Estimand.** `S_diff(A)` as §3.1 — primary. `S_within`, `S_plane` —
   secondary, separate tables, no promotion. *Drafted.*
2. **Population.** Operator families and their membership rule; the minimum
   fleet size; the shell-matched control construction and its matching factors;
   the objects that could not be assigned, published. *Partly drafted (§4).*
3. **Channels.** Phase primary, epoch secondary, with the phase recovery
   added to `cadence_core` first. Each channel independently corrected. *Drafted.*
4. **Statistics.** Rayleigh `R` and staggered-phase `R_K`; pairwise
   cross-correlogram with its lag bins and coincidence window `delta`. **OPEN:**
   `delta` is a free parameter and must be fixed from the sampling geometry —
   it cannot be smaller than the element-set cadence that resolves it, and T3's
   §0.1 gives the numbers to fix it from (payload median spacing 0.3989 d).
5. **Null.** Per-object circular shift, resample count, seed. *Drafted (§3.3).*
6. **Space weather.** Either the ingested Ap/F10.7 arm, or an explicit
   registered statement that it was not available and that §3.1's control set
   is the only handle. **OPEN and blocked on the ingest of §3.4.**
7. **Recall.** The injection–recovery design, its amplitude grid, its strata,
   and the minimum-detectable-synchrony calculation that follows from it —
   **computed and published before the synchrony numbers**. *Drafted (§5.2);
   the amplitude grid is OPEN.*
8. **Multiple testing.** Across operators, across planes, across lag bins,
   across the two channels. The T3 registration's three-level treatment is the
   template. **OPEN.**
9. **Acceptance / stop rules.** What counts as a synchrony finding; what counts
   as "below the detection floor"; the prohibition on re-running with a
   different `delta` or a different null after seeing a number; the rule that
   an unwelcome result is reported. **OPEN.**
10. **Blind spots, declared in advance.** At minimum: continuous low-thrust
    fleets are invisible to both channels for the same reason they are invisible
    to T3; staggered commanding is invisible to `R` and is the reason `R_K`
    exists; sub-2-day coordination is below the archive's resolution; and
    `object.name` is the only operator evidence we have, so a fleet that renames
    or that flies under mixed designations is mis-assigned. *Drafted.*
11. **Resource bounds and the GPU path**, matching T3's §13. *Drafted by
    reference.*
12. **Scope fence.** T4 changes no shipped threshold, relabels no object, and
    touches no other track's files. *Drafted by reference to T3 §11.*

## 8. Honest summary

T4 is a real question with a clean primary design — a *difference* in synchrony
against a shell-matched control, on a phase channel that avoids the recall
penalty — and two hard dependencies that do not exist yet:

1. **T3 must be extended to record the fitted phase**, which it computes and
   currently throws away. Small, additive, and the first implementation task.
2. **Detection recall must be measured**, because without it the epoch channel
   can produce a null result that means nothing. The injection–recovery design
   of §5.2 is the cheapest honest way, and it is worth doing whether or not T4
   ever runs.

And one prerequisite that is currently a hole: the archive's geomagnetic table
holds six hours of data, so the shared-drag confound cannot yet be conditioned
on directly and must be carried entirely by the control-set difference.

None of this is registered. When it is, it will be registered alone, first.
