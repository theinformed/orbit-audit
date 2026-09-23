# Pre-registration: the corrected floor, the derived multiple, and a read of the period discrepancy

**Track:** T10 (fuel-burn efficiency), T10c follow-up, second registration.
**Owed by:** `docs/t10c-cycle-deadband-results-20260922.md` §8 items 1, 2, 3 and 5
— the corrected surrogate, a floor multiple derived rather than chosen, the
period discrepancy, and the F2 comparison on the unscreened population.
**Binding parent registrations:**
`docs/t10c-cycle-deadband-preregistration-20260922.md` (commit `0a49ba5`), whose
estimator, screens G1–G5, segmentation and per-cycle reads are reused
**unchanged**, and through it
`docs/stationkeeping-efficiency-preregistration-20260922.md` (`f0f2b41`) §4,
whose triaxial acceleration and drift-cycle derivations are imported and not
restated.
**Status:** written and committed ALONE, before any number it describes exists.

---

## 0. What this registration is, and the one thing it cannot be

### 0.1 What the first registration got wrong

The first T10c cycle registration built its floor screen (G6) on a surrogate
(F1) that permuted each station segment's longitude residuals **about the
segment centre**. Those residuals contain the sawtooth itself, so the surrogate
kept the signal's amplitude and destroyed only its order: F1 measured the
**segment envelope**, which is the quantity the whole track exists to get
underneath. It came out at `0.0333 deg`, 1.6 times **larger** than the
`±0.0208 deg` box the 14.00-day line implies, and screening at `3 × F1` discarded
183,360 of 184,591 cycles. The registered screen made the registered question
unanswerable by construction. Two further defects followed from it: D2 (median
survivor `>` 3× floor) could not fire, because G6 already required exactly that
of every admitted cycle; and the `3 ×` multiple itself was chosen in "sigma"
units for a statistic — the range of `m` samples — whose sampling distribution is
not a standard normal, so it could not admit a real signal sitting at twice its
floor.

### 0.2 What this registration fixes, in order

1. A **noise**-floor surrogate: residuals about the **fitted sawtooth**, so the
   amplitude is removed rather than preserved (§2), with its expectation derived
   in closed form (§2.2) and a falsifiable cross-check against that expectation
   (§2.3).
2. A **derived** floor multiple, from the measured longitude scatter and the
   cycle's own sample count, with a fixed false-admission rate (§3).
3. A **non-circular** floor-separation criterion, replacing the vacuous D2 (§5).
4. The F2 never-manoeuvred comparison on the **unscreened** population as well
   as the screened one (§4.3), which the first run computed only for the
   carriers.
5. A registered read of the **period discrepancy** — 9.94 d measured against
   T3's 14.00 d — with three mechanisms derived to distinct, separating
   predictions, and an arm that can move the answer (§6).

### 0.3 The thing this registration cannot be, stated plainly and first

**This is a confirmatory re-registration on data that has already been read
once.** The first run published, as UNREGISTERED and NOT CLAIMED, a per-object
median box of `0.0203 deg [0.0188, 0.0212]` on 207 of 208 carriers. That number
exists. Nothing written here can make this run blind, and no wording will be used
that pretends otherwise.

What a registration can still do on already-seen data, and what this one is
built to do:

* **Fix every constant by derivation rather than by choice.** The floor is
  `0.5 sigma_lambda x` a quantile of a range statistic; the multiple is the ratio
  of two quantiles of that same statistic at a false-admission rate fixed here
  (§3.2); the expected-range constants are computed at run time from the normal
  distribution, not looked up. No constant in this document was selected by
  asking whether it admits `0.0203`, and §3.3 states the one place where that
  choice is load-bearing and registers the sensitivity that exposes it.
* **Carry falsifiable checks that can fail on this data.** Five of them: the
  surrogate-versus-expectation check D5 (§2.3), the unscreened F2 separation D3
  (§4.3), the registered prediction that D4 **fails again** and that the merge
  arm moves it (§5, §6.4), the noise-contamination bound D2v2 (§5), and the
  three-way period discrimination (§6), whose measured point can land on any of
  three branches or none.
* **Say so in the claim.** Every sentence in the results document that states the
  measured box must carry the words **"registered after the first read of this
  quantity"**. That phrase is registered here and is not optional.

**It follows that this registration cannot convert the agreement with T3 into an
independent confirmation.** T3's `±0.0208 deg` is independent of this instrument
— a Lomb–Scargle line in mean motion, inverted through `T = 4 sqrt(R/A)` — and
that independence is real and is what makes the comparison worth making. The
non-independence is between **this run and the first run**, which share data,
population and instrument. The results document must not blur those two.

---

## 1. Inputs, population, and what is not touched

### 1.1 Inputs, hash-pinned — the parent's four, unchanged

| Input | Path | sha256 |
| --- | --- | --- |
| Archive snapshot, read-only | `/tmp/eol-study-20260920/archive.sqlite3` | `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` |
| T3 per-object artifact (the line roster) | `docs/cadence-results-20260921.jsonl` | verified at run time |
| Detected event set (T2's run) | `/tmp/t2-repricing-20260921/events.jsonl.gz` | `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f` |
| Propulsion catalogue | `data/propulsion-catalog-v1.json` | `7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9` |

The event set is read for one purpose only — the commercial-civil membership
test of §1.3. **No detected event enters the estimator at any point**, which is
the property that got the first run under the 73.8-day detected cadence and is
not relaxed here.

### 1.2 Population — identical to the parent registration

T3's 14.00-day line carriers, reconstructed from the committed per-object
artifact by the parent registration §1.2 rule, asserted to reproduce **214
objects, 208 GEO, 6 LEO** (stop rule S2). The primary population is the 208 GEO
carriers. The F2 arm is the **331 GEO objects of class `passive`** in the same
committed artifact, asserted to carry zero detected events (S3).

### 1.3 Policy

Unchanged and restated because it is a stop rule, not a convention. For every
carrier this track measures **angles and times only**. No delta-v, propellant
mass, Isp, lifetime or fuel quantity is computed, reported or named for any
object outside `data/propulsion-catalog-v1.json`, whose `policy` field must read
`commercial-civil-only` or the run stops. The code raises rather than returns if
asked otherwise (§7.1 test 14).

### 1.4 What is NOT touched

Detection; the production sweep; the published site artifacts; Paper A and Paper
B; T3's own line result, read and never recomputed; the parent registration's
§4 derivations; **and the first T10c cycle registration itself, which is not
edited.** Its defects are recorded there in its results document and repaired
here in a new document, which is the rule.

---

## 2. The corrected surrogate — a noise floor, and its expectation derived

### 2.1 The construction

Within each station segment (parent screen G2), the registered swing filter of
parent §2.2 is run on the **real** drift-rate series with the registered
`k = 5 sigma_rate`, giving the segment's runs. Parent §2.1 derives what a run is:
inside the box the longitude acceleration is constant, so `lambda(t)` is a
parabola and `lambda_dot(t)` is a straight ramp. Fit those forms, by ordinary
least squares, **within each run**:

    lambda_hat(t)     = c0 + c1 t + c2 t^2                                 (F1)
    lambda_dot_hat(t) = b0 + b1 t                                          (F2)

and take the residuals `e_k = lambda_k - lambda_hat(t_k)` and
`f_k = lambda_dot_k - lambda_dot_hat(t_k)`. **The fitted sawtooth carries the
whole box**: (F1) is the exact shape the derivation predicts for a cycle, so what
is left after subtracting it is the element noise and whatever the parabola does
not describe — and, by construction, none of the excursion.

The surrogate for that segment is then built by permuting the pooled residuals
in time, seed `20260922`, keeping the original epochs:

    lambda^s_k     = median(lambda_segment)   + e_{pi(k)}                   (F3)
    lambda_dot^s_k = mean(lambda_dot_segment) + f_{pi(k)}                   (F4)

and the identical finder and estimator are run on it. **The difference from the
registered F1 is one word: the residuals are taken about the fitted sawtooth, not
about the segment centre.** That is the whole repair, and it is the difference
between destroying the signal and merely shuffling it.

### 2.2 Its expectation, derived

If the residuals are white with scale `sigma_lambda`, the surrogate series is
i.i.d. about a constant. Any run of `m` samples the finder isolates from such a
series has a peak-to-trough distributed as `sigma_lambda W_m`, where `W_m` is the
**range of `m` independent standard normals**. Since the positional read is half
the peak-to-trough (parent eq. 20),

    E[ R_pos^surrogate | m ]      = 0.5 sigma_lambda E[W_m]  = 0.5 sigma_lambda d2(m)   (23)
    median[ R_pos^surrogate | m ] = 0.5 sigma_lambda med(W_m)                            (24)

with `d2` the control-chart constant. Both `d2(m)` and `med(W_m)` are computed at
run time by Monte Carlo at a fixed seed rather than taken from a table, so
nothing here rests on a number a reader cannot reproduce, and §7.1 test 2 asserts
the computed `d2` against the published control-chart values.

`sigma_lambda` is **measured on this population**, by the second-difference MAD
estimator of parent §3.1 applied to mean longitude: the second difference of a
locally linear series is pure noise with variance `6 sigma^2`, so the scatter is
read off the data without needing a quiet arc. The first run measured
`sigma_lambda = 0.0066541 deg` over this population and a modal cycle sample
count `m = 12`, giving `0.5 x 0.0066541 x 3.2562 = 0.010833 deg`
<!-- src: docs/t10c-cycle-deadband-20260922-receipt.json, floorDerivedElementNoise -->.
Those published figures are what §3 derives its multiple from; the run
**re-measures** `sigma_lambda` and uses its own value, and a disagreement with the
published one by more than 10% is reported as a defect in one of the two runs
(§7.3 D2).

### 2.3 D5 — the check that can fail

The finder does not sample runs at random: it cuts where the drift rate reverses
by more than `k sigma_rate`, which selects. On a permuted series the reversals are
noise, so the surrogate's runs are short, and its `m` distribution is **not** the
real population's. Comparing pooled medians would confound the two effects, so
the registered check is made **at matched sample count**:

> **D5.** For the modal surrogate sample count `m*`, the ratio
>
>     rho_5 = median( R_pos^surrogate | m = m* ) / ( 0.5 sigma_lambda med(W_{m*}) )
>
> must lie in `[0.70, 1.40]`.

`rho_5` is a direct test of the claim §2.1 makes — that the residuals about the
fitted sawtooth are noise. A surrogate still carrying structure returns
`rho_5 > 1.40`; one whose residuals have been over-fitted returns `rho_5 < 0.70`.
The band is registered here and the ratio is reported whatever it is. **If D5
fails the surrogate is reported as still not a noise floor, in those words, and
the screen falls back to the derived floor of §3, which does not depend on the
surrogate at all.** That fallback is registered in advance so it cannot be
invented afterwards.

The surrogate is reported with its counts, its `m` distribution, and its
quantiles beside every distribution. It is **not** the screen. §3 is the screen.

---

## 3. The floor and the multiple, both derived

### 3.1 The screen

Screen **G6v2**, evaluated per cycle `j` at that cycle's own sample count `m_j`:

    R_pos,j  >=  0.5 sigma_lambda q_{1-alpha}( W_{m_j} ),      alpha = 0.01.  (25)

**Derivation.** Under the hypothesis that cycle `j` is noise, its positional read
is exactly `0.5 sigma_lambda W_{m_j}` by the argument of §2.2. Requiring (25)
therefore admits a noise-only cycle with probability exactly `alpha`. The screen
is a **false-admission rate**, which is a quantity with a meaning, rather than a
multiple of a floor, which is not.

Expressed as a multiple of the floor **median** — the form the first
registration used, so the two are comparable — (25) is

    c(m) = q_{1-alpha}(W_m) / med(W_m),                                     (26)

a pure property of the normal distribution. At `alpha = 0.01`:
`c(5) = 2.04`, `c(8) = 1.79`, `c(12) = 1.65`, `c(20) = 1.53` (Monte Carlo,
`2 x 10^5` draws, seed `20260922`; the run recomputes them and §7.1 test 3
asserts the table it uses).

### 3.2 Why `3 x` could not work, derived rather than asserted

`3 x med(W_12)` is `W > 9.6`. The tail probability of the range of twelve
standard normals exceeding 9.6 is of order `10^-9`. A screen at that level admits
only cycles whose excursion is many times the element noise, which is to say it
is not a noise screen at all — it is an amplitude cut set nine orders of
magnitude beyond the noise. **The error was applying a "3 sigma" intuition to a
statistic that is not a standard normal**: the range of `m` samples already has a
mean of `3.26 sigma` at `m = 12`, so multiplying its median by three asks for a
`9.6 sigma` excursion. That is the whole diagnosis, and it is a property of the
distribution and not of the data.

### 3.3 Where the choice of `alpha` is load-bearing — declared in advance

`alpha` is fixed at the conventional **0.01** and the run's primary uses it. The
declaration owed here: at `alpha = 0.001`, `c(12) = 1.90`, and the first run
reported its measured box at **1.87** times the derived floor median. **A screen
at `alpha = 0.001` would therefore sit essentially exactly on the known signal.**
That is stated now, before the run, so that the choice of `alpha = 0.01` cannot
be presented afterwards as innocent of it.

Registered sensitivity, reported in the results document as a table whatever it
shows: the whole primary analysis is repeated at `alpha in {0.05, 0.01, 0.001}`
and the resulting per-object median box, its interval, and the admitted cycle
count are published for each. If the answer moves materially across that range,
the screen is doing the work and the results document says so in the first
paragraph.

### 3.4 The contamination bound, which is what D2 should have been

`alpha` per cycle over `N_G6` cycles entering G6v2 admits an expected
`alpha N_G6` noise cycles. The run reports

    contamination = alpha * N_G6 / N_admitted,                              (27)

the expected fraction of the admitted set that is noise. This is computable, it
is not circular, and it is the honest form of the question the vacuous D2 was
trying to ask.

---

## 4. What is measured and reported

### 4.1 Per cycle, per object, per population

Unchanged from the parent registration §4: per cycle `R_pos`, `R_rate`,
`A_cycle`, `T_cycle`, `Delta lambda_dot`, the sample count, the slot longitude,
`A(lambda)`, `R_pred = A(lambda) T^2 / 16`, and every screen flag, in the JSONL;
per object the medians over its resolved cycles; per population the distribution
of per-object medians with a non-parametric bootstrap 95% percentile interval,
`B = 10000`, seed `20260922`, **resampling objects**.

### 4.2 The comparisons

* Against T3's `±0.0208 deg`: the interval, whether it contains that figure, and
  the count of carriers within a factor of two of it (`[0.0104, 0.0416]`).
* Against each object's own `R_pred` at its own slot: the ratio `R_pos/R_pred`,
  which is the statistic §6 turns into a discriminator.
* Against 14.00 days: the `T_cycle` distribution and the count in `[7, 28] d`.
* The internal check `R_rate` on `R_pos` (D4) and the free-drift control
  `A_cycle` on the derived `A(lambda)`, both Theil–Sen with bootstrap intervals
  over objects, both with a registered prediction of slope 1.

### 4.3 F2, on the unscreened population as well — the owed item

The first run compared carriers against never-manoeuvred passives with both arms
passing through the same (mis-specified) G6 screen, and left the unscreened
comparison owed. **Registered here:** the F2 comparison is computed and reported
**twice** — once on the G6v2-admitted cycles of each arm, and once on the
population passing G3–G5 only, with no floor screen at all, for both arms. Both
intervals are published. D3 (§5) requires separation on **both**.

---

## 5. Acceptance criteria and the decision rule, fixed before the numbers

All evaluated on the GEO line carriers.

* **D1 power.** At least **20** carriers with at least **3** resolved cycles
  each. Otherwise **UNDERPOWERED**, in that word.
* **D2v2 floor, non-circular.** Two conditions, neither of which the screen can
  force: (a) T3's independently derived `0.0208 deg` **exceeds** the derived
  floor median `0.5 sigma_lambda med(W_m*)` — a statement about the target,
  decidable before a single cycle is admitted; and (b) the contamination of
  (27) is **below 0.10**. If either fails the verdict is **NOISE-DOMINATED**, in
  that word, and no comparison is made.
* **D3 not a natural libration.** The carriers' and the passives' bootstrap
  intervals must be disjoint on **both** the admitted and the unscreened
  populations (§4.3). Otherwise **NOT DISTINGUISHABLE FROM AN UNCONTROLLED
  OBJECT IN A SLOT**, in those words.
* **D4 internal agreement.** The `R_rate`-on-`R_pos` slope interval contains 1.
  **Registered prediction, stated in advance: D4 will fail again**, at a slope
  well below 1, because the splitting mechanism of §6 corrupts both the ramp
  amplitude and the fitted acceleration that eq. (21) is built from. Its
  registered consequence is unchanged — the positional estimator is reported
  alone and the disagreement is stated in the same sentence — and §6.4 registers
  the discriminating consequence: **if splitting is the cause, the merge arm's D4
  slope must move toward 1.** If D4 fails and the merge arm does **not** move it,
  that prediction is wrong and the results document says so.
* **D5 surrogate.** §2.3.

**The verdict table.**

| Condition | Verdict, in these words |
| --- | --- |
| D1, D2v2, D3, D5 all pass, and the bootstrap interval on the per-object median contains `0.0208 deg` | "The cycle-resolved flown-excursion box on T3's own line carriers is [value] [interval], measured by a registered estimator whose floor is derived from the measured element noise. T3's independently derived ±0.0208 deg lies inside that interval. **CLAIMABLE**, with the §0.3 declaration: this registration was written after the first read of this quantity, so the agreement with T3 is an agreement between two independent instruments but not between two independent analyses of these data." |
| D1, D2v2, D3, D5 all pass and the interval excludes `0.0208 deg` | "The box is [value] [interval] and it **excludes** T3's ±0.0208 deg. The measurement is CLAIMABLE and the disagreement is reported, not explained." |
| D1, D2v2 or D3 fails | the named verdict word, no comparison at all. |
| D5 fails | the surrogate is reported as still not a noise floor, the derived floor of §3 remains the screen, and the verdict row above applies with that stated in the same paragraph. |
| D4 fails | reported alongside whichever row applies, in the same sentence, together with the merge-arm outcome of §6.4. |

**What CLAIMABLE means here and nothing more.** It means the number is produced
by a registered rule whose floor is derived, whose screens were fixed before the
run, and whose falsifiable checks were passed. It does not mean the estimand is
the licensed deadband: every number in this track is a **flown excursion**, and
an operator holding a `±0.05 deg` licence inside `±0.01 deg` of actual motion is
measured at `0.01`. That sentence must appear wherever the box appears.

---

## 6. The period discrepancy, registered as a three-way discrimination

The first run measured a box that matches T3 (`0.0203` against `0.0208`) and a
period that does not (`9.94 d` against `14.00 d`), with the measured box a median
**2.66 times** what its own measured cycle predicts through `R = A T^2 / 16`.
Registered here: three mechanisms, each derived to a **triple** — the apparent
period, the apparent box, and the ratio `R_pos/R_pred` — and the triples separate.

Let `(T*, R*)` be a true one-burn cycle, so `R* = A T*^2 / 16` by parent eq. (16).

### 6.1 M1 — one burn per cycle, correctly segmented

Measured triple `(T*, R*, 1)`. This is the parent registration's model and the
null of this section.

### 6.2 M2 — a clean burn pair a half-cycle apart

Two equal resets per natural cycle. The observable cycle becomes `T*/2` and its
excursion `R*/4`, because `A (T*/2)^2 / 16 = R*/4`. **Write the prediction
plainly, since it is what the first results document named and left untested:
a burn pair halves the cycle AND quarters the box.** Its triple is therefore

    ( 0.5 T*,  0.25 R*,  1 ).                                               (28)

**The relation `R = A T^2/16` is invariant under pairing.** A clean pair is
algebraically nothing but a one-burn sawtooth at half the period, so it cannot
move `R_pos/R_pred` off 1 at all — whatever it does to the period. **A measured
ratio materially different from 1 refutes clean pairing as the explanation of the
discrepancy, on algebra, before any count is taken.** The first run measured
`2.66`, and this registration says in advance that if the ratio comes back near
`2.66` again, M2 is refuted and not merely disfavoured.

M2 is independently excluded in this channel by measurement, and the consistency
is registered here rather than discovered later:
`docs/harmonic-mechanism-results-20260922.md` scanned every two-burn split reset
at every separation and every impulse ratio — `0 of 5,940` cells — and measured
eight two-burn arms, every one of which inverts the third harmonic along with the
second, against a carrier signature of `(pi, 0, pi, 0)`. Its symmetric case
(`s = 0.50`, `rho = 1`) returns `F_1 = 0.50` with the odd harmonics gone, which is
the **same statement as (28) from the other side**: a clean pair is a half-period
one-burn sawtooth, so its fundamental moves to `2/T*`. **Two independent routes
exclude the same family in the east-west channel, and the results document must
say so.**

### 6.3 M3 — cycle splitting by the prominence filter

A noise reversal inside a ramp, exceeding `k sigma_rate`, cuts one true cycle into
two runs. Derive the consequence exactly. With
`lambda(t) - lambda_0 = lambda_dot_0 t - A t^2/2`, `lambda_dot_0 = 2 sqrt(A R*)`
and `T* = 4 sqrt(R*/A)`, substitution gives

    lambda(phi T*) - lambda_0 = 8 R* phi (1 - phi),        0 <= phi <= 1.    (29)

For a split at `t* = phi T*` with `phi <= 1/2` (the rising side):

* **run 1** spans `[0, phi T*]`, is monotone, and has
  `R_pos = 4 R* phi (1-phi)` against `R_pred = A (phi T*)^2/16 = phi^2 R*`, so

      R_pos / R_pred  =  4 (1 - phi) / phi.                                  (30)

* **run 2** spans `[phi T*, T*]`, contains the vertex, so its extremes are `2R*`
  and `0`: `R_pos = R*` against `R_pred = (1-phi)^2 R*`, so

      R_pos / R_pred  =  1 / (1 - phi)^2.                                    (31)

At the vertex, `phi = 1/2`, both give **4**: each half-run has the full box `R*`
and half the period, so the apparent box is unchanged while the apparent period
halves. M3's triple is therefore

    ( < T*,  ~ R*,  > 1 ),   and at a vertex split exactly ( 0.5 T*, R*, 4 ). (32)

(30) and (31) both exceed 1 for every admissible `phi`, and G3/G4 remove the
short runs where they diverge. **Splitting always pushes the ratio above 1 and
the period below `T*`, while leaving the box roughly alone.**

### 6.4 The merge arm — the part that can move the answer

The three triples separate: `(1, 1, 1)`, `(0.5, 0.25, 1)`, `(<1, ~1, >1)` as
fractions of `(T*, R*)` and the ratio. The first run's measured point,
`(0.71, 0.98, 2.66)`, is on the M3 branch by inspection — but inspection is not a
test, so this registers one.

**Registered split detector.** The swing filter alternates direction: a true
sawtooth presents as a long ramp, then a short opposite-direction run which is
the burn jump itself. A boundary is a **candidate split** when the intervening
opposite-direction run's drift-rate excursion is less than `rho = 0.50` times the
mean ramp amplitude of the two flanking runs — a noise reversal is a few sigma,
a real burn reset is the size of the ramp it undoes, and `rho = 0.50` sits
between them. `rho in {0.25, 0.75}` are registered sensitivities.

**Registered merge arm.** Flanking runs across candidate splits are merged,
transitively, and `R_pos`, `T_cycle`, `R_pred`, `R_rate` and `A_cycle` are
recomputed on the merged runs under the identical screens. Registered
predictions, all four reported whatever they show:

* **(a)** the median `T_cycle` **rises** toward 14.0 d;
* **(b)** the median `R_pos` stays within a factor of **1.3** of the unmerged
  value;
* **(c)** the median `R_pos/R_pred` **falls** toward 1;
* **(d)** the D4 slope (`R_rate` on `R_pos`) **moves toward 1**.

**Registered reading, fixed now:**

| Outcome | Reading, in these words |
| --- | --- |
| (a) and (c) both move as predicted | "The period discrepancy is **cycle splitting by the prominence filter**, measured: merging candidate splits moves the period from [x] to [y] days and the box-to-prediction ratio from [p] to [q]." |
| (a) or (c) does not move | "The period discrepancy is **NOT explained by splitting** and remains unexplained. M2 is refuted by algebra and by the harmonic-mechanism measurement; M1 is refuted by the ratio; what is left is that the one-sided parabolic cycle is not the waveform these objects fly, and this track does not know what is." |
| (b) fails — the box moves by more than 1.3x | the merge arm is reported as changing the estimand, not repairing it, and the unmerged primary stands alone. |

The merge arm is a **registered companion**, never the primary. The primary
per-object box reported in the verdict of §5 is the unmerged one, under G6v2.

### 6.5 A prominence sweep, registered as the independent view of the same question

The whole primary is repeated at `k in {3, 5, 8, 12, 20}`. Under M3, raising `k`
suppresses splits, so the median `T_cycle` must rise monotonically with `k` and
the median `R_pos/R_pred` must fall. Under M1 or M2 both are flat in `k`. The
sweep is reported as a table with those two registered predictions printed beside
it.

---

## 7. Implementation, proofs, compute

### 7.1 Offline proofs required before any result document is written

No archive, no network, no event set; every fixture constructed in the test.

1. **The corrected surrogate removes the amplitude.** On a synthetic exact
   sawtooth of known `(R, A)` plus noise of known `sigma`, the residuals about
   the fitted (F1) have a measured scatter within 15% of `sigma`, and the
   residuals about the **segment centre** — the first registration's F1 — have a
   scatter at least 3 times larger. The defect and its repair are both asserted.
2. **`d2(m)` is the control-chart constant**: the computed `E[W_m]` matches the
   published `d2` for `m = 2, 5, 10` to within 1%.
3. **The multiple table of (26)** is monotone decreasing in `m`, and
   `c(12)` at `alpha = 0.01` lies in `[1.55, 1.75]`.
4. **(25) has the registered false-admission rate**: on `10^5` synthetic pure-
   noise cycles of `m = 12` samples at a planted `sigma_lambda`, the admitted
   fraction is `0.01 +/- 0.002`.
5. **(29) is the parabola**: the closed form `8 R phi (1-phi)` matches a direct
   evaluation of the parent's cycle to `1e-12` relative, over `R` in
   `{0.005, 0.0208, 0.05}` and three accelerations.
6. **(30) and (31) are the split ratios**: a synthetic exact cycle cut at
   `phi in {0.2, 0.35, 0.5, 0.65}` returns `R_pos/R_pred` matching (30)/(31)
   within 3%, and at `phi = 0.5` returns 4 within 3%.
7. **M2's invariance**: a synthetic two-burn cycle at half the period and a
   quarter of the box returns `R_pos/R_pred = 1` within 2%, and its measured
   period is half and its measured box a quarter of the one-burn case. **(28)
   asserted, not argued.**
8. **The split detector separates**: on a synthetic series with planted noise
   reversals and planted burn resets, every planted burn boundary is classified
   not-a-split and every planted noise reversal is classified a candidate split,
   at `rho = 0.5`.
9. **The merge arm recovers the planted cycle**: a synthetic sawtooth whose
   cycles are artificially split returns, after merging, the planted `R`, `T` and
   a ratio of 1 within 5%.
10. **The merge arm is a no-op on clean data**: on an unsplit synthetic sawtooth
    it changes no run boundary.
11. **The unscreened F2 path computes both arms** on constructed miniature
    inputs and reports two intervals, asserted distinct fields.
12. **The parent's estimator is imported unchanged** — `swing_runs`,
    `cycles_in_segment`, the membership rule and the `sigma` estimators are the
    committed functions, asserted by identity against
    `tools/t10_followup_deadband_cycles.py`, so no screen is silently re-tuned.
13. **The line-carrier membership rule reproduces the committed counts** from a
    constructed miniature artifact, and flags a mismatch.
14. **The policy gate**: asking for a delta-v on a NORAD outside the
    commercial-civil catalogue raises, and the catalogue's `policy` field is
    still a stop.
15. **`R_pred` reproduces T3's table**: `A_max T^2/16` at `T = 14.0 d` gives
    `0.0208 deg` and at half `A_max` gives `0.0104 deg`, to `1e-9`.

### 7.2 Compute

CPU only, on `pc`, read-only against the archive. Several passes over the same
208 carriers plus the 331-object passive arm; element states are read once and
cached. No GPU arm is built, so no `gpu-consumers.json` row is owed. Wall, CPU
and peak RSS are recorded whatever they are.

### 7.3 Stop and defect rules

* **S1** — any input hash mismatch: stop.
* **S2** — the line-carrier rule does not reproduce 214 / 208 GEO / 6 LEO: stop.
* **S3** — any passive-roster object carries a detected event: stop the F2 arm,
  report the roster as not passive, run the rest.
* **S4** — the archive opens writable: stop.
* **S5** — any object outside the commercial-civil catalogue acquires a delta-v,
  propellant or fuel quantity: stop.
* **D1** — a defect found in this registration's own algebra by the test suite is
  reported in the results document with its size, both forms are published, and
  **this registration is not edited**.
* **D2** — the re-measured `sigma_lambda` disagrees with the first run's
  published `0.0066541 deg` by more than 10%: reported as a defect in one of the
  two runs, with both values, and the run continues on its own measurement.

---

## 8. Blind spots, named before the measurement

* **The estimand is flown excursion, not licensed box.** Unchanged and restated
  in §5.
* **This is not a blind analysis.** §0.3, and it is the largest limitation in
  the document.
* **The one-burn parabola is still the model.** M3 repairs a segmentation
  failure; it does not test whether the waveform is a one-sided parabolic cycle
  at all. If the merge arm fails to move the ratio, that is what is left, and §6.4
  registers those words.
* **The line carriers are not a random sample of GEO.** They are the objects
  whose mean-motion periodogram carries a 14.00-day peak, which selects for
  regular, detectable manoeuvring; the measured box is a regular east-west
  keeper's box, and the bias runs toward tighter boxes.
* **The draconitic-year longitude oscillation is not subtracted.** It is slow
  against a 10-day cycle and enters as a baseline, but it is part of `R_pos` and
  part of what the (F1) parabola absorbs into the surrogate's residuals — which
  would make the surrogate's `rho_5` larger, not smaller, and D5 is the check
  that would see it.
* **Carriers at high inclination.** 17 of 208 sit at 5 degrees or more, including
  T3's top three named carriers; they are not routine east-west keepers and their
  box is reported separately, as the parent registration required.
* **`sigma_lambda` is one number for a population.** A per-object scatter would be
  better and the archive does not carry a per-element covariance; T5c owes it.
  Using a population figure makes the per-cycle screen (25) slightly wrong in both
  directions, object by object, and that is named rather than corrected.

---

## 9. Deliverables

* `docs/t10c-cycle-deadband-v2-results-20260922.md` — the results document, with
  the §5 verdict in its first paragraph and the §0.3 declaration in the same
  paragraph as any claimed number.
* `docs/t10c-cycle-deadband-v2-20260922.jsonl` — per cycle, per object, the
  surrogate, both floors, and the merge arm.
* `docs/t10c-cycle-deadband-v2-20260922-receipt.json` — inputs and hashes, seeds,
  census, the derived floor and multiple table, the contamination bound, the
  acceptance criteria, the slopes with intervals, the period discrimination
  table, the runtime proofs, wall/CPU/RSS.
* `tools/t10c_v2_deadband_floor.py` — the instrument.
* `tests/test_orbit_t10c_v2_floor.py` — the §7.1 proofs.
* One row in `docs/research-program-runbook-20260921.md` under T10.
