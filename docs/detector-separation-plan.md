# Closing the separation gap — plan to make the orbit detector excellent

**Written 2026-09-11. Approved by Sean the same day.** Figures measured from the
live published artifact `orbit-events-30c435b7ec87696d.json` (built
2026-09-10T03:40:41Z) unless stated.

---

## BLOCKING DEFECT, FOUND 11 SEP — THE LANE CANNOT PUBLISH AT ALL

This outranks everything else in this document.

Three consecutive runs were killed by systemd on 11 Sep, exactly 2h30m apart:

    10:55:44  orbit-release.service: start operation timed out. Terminating.
    13:25:46  orbit-release.service: start operation timed out. Terminating.
    15:55:48  orbit-release.service: start operation timed out. Terminating.

The SWEEP budgets itself and checkpoints correctly. The **tail does not**, and
`TimeoutStartSec=9000` applies to the whole service. So every run walks the
archive across several slices, completes the pass, begins the tail, and is
SIGTERMed before it writes anything.

The published artifact is **over 40 hours old** while the lane reports itself
enabled, active and healthy. Every successful publish on record has been a
MANUAL unbudgeted run, which has no systemd timeout. This is also why the
watchdog shows green: the unit fails at the END of a run, not at the start.

**Do not raise `TimeoutStartSec`.** The unit file documents this exact failure
twice (2026-08-13, 2026-08-18) and instructs: *"the answer is to make the tail
resumable too, not to raise this again."* The tail has now grown past it, so the
documented answer applies. The resumable-tail work was scheduled on 11 Sep.

---

## The gap, in one number

| | |
|---|---|
| Separation measured | **6.74x** |
| Separation required | **10.0x** |
| False-alarm floor | 0.45 per 1,000 (39,924 flags / 89.2 M intervals, 12,469 objects) |
| Payload flag rate | 3.06 per 1,000 (191,700 flags / 62.6 M intervals, 18,751 payloads) |
| False-alarm design target | **PASSES** — Jeffreys 95% upper 0.00045 against a 0.001 ceiling |

The floor is already excellent. The gap is entirely on the payload side: too
much of the 3.06 could still be the same noise. That is why the site says
*candidate*, and it is the correct thing to say.

### Two routes, and one trap

| Route | Required move | Verdict |
|---|---|---|
| Cut the false-alarm floor | 0.452 -> 0.305 per 1,000 (-33%) | Possible, only if TARGETED |
| Raise the payload catch | 3.05 -> 4.52 per 1,000 (+48%) | More promising |
| Tighten the detector overall | both rates fall together | **Does nothing** — ratio barely moves |

The last row is the trap. A symmetric squeeze moves both populations. Every
change must be **asymmetric**: it must hurt noise more than signal, and we
should be able to say why in physics before measuring.

### Correction — persistence is ALREADY done

I initially called persistence the highest-value remaining work. It is not. It
is already in the self-history lane at `orbit_campaigns.py:1331`, two-day
horizon, 0.5 survival fraction. **The 6.74x is measured with it on.** The
historical 13.9 -> 1.83 improvement it delivered is already banked. Nobody
should rebuild it.

---

## Phase 0 — decompose both populations  *(SHIPPED 11 Sep, commit efee915)*

We knew the two rates and had never looked at what they are MADE of. Both
remaining routes need to know which channels, signatures and regimes carry the
flags.

Implemented as pure accounting at zero extra archive cost: `ArchivePass.note()`
already receives the flagged events, and each carries its signature, regime,
perigee and tripped channel tests. Six dimensions, passive and payload counted
apart: signature, channel, channel COMBINATION, regime, perigee band,
confidence.

`channelCombination` is the diagnostic one. "inclination alone" and
"semiMajorAxis+inclination" are different findings — the first is what a badly
conditioned channel looks like, the second is what a real burn looks like.

Includes `ArchivePass.__setstate__`, which backfills fields missing from
checkpoints written by earlier builds. Pickle restores `__dict__` directly and
dataclass defaults do NOT apply; without it, new code meeting an old checkpoint
raises AttributeError, the loader discards it, and a sweep 68,000 objects deep
restarts from zero. A test pins this.

**Awaiting data**: the breakdown appears in `controls.*.breakdown` on the next
successful publish — which is gated on the blocking defect above.

**Done when:** we can name the top three contributors to the floor and state
what fraction each accounts for.

## Phase 1 — raise the numerator: the station-keeping blind spot

A satellite holding altitude with thrust cancelling drag is **invisible**. Its
own measured drag baseline absorbs the thrust, the residual is zero, nothing
trips. That case already exists in the code as a labelled `gap` rather than a
false negative.

This is the largest known population of real, undetected payload manoeuvres —
constellation satellites doing it continuously, and Starlink alone is already
775 of the 1,500 published events. **Debris cannot produce this signal**, so it
is asymmetric by construction.

*Mechanism:* compare observed decay against a ballistic-coefficient prediction
rather than the object's own history. Decaying markedly slower than B* implies
thrust.

*Risk, stated up front:* needs an independent drag model, importing model error
the self-history lane deliberately avoids. Must carry an honest evidence class,
not be folded in quietly beside measured quantities.

**Done when:** payload rate rises materially with the floor flat, measured on
the control curve.

## Phase 2 — cut the denominator where Phase 0 says it lives

One hypothesis is already visible in the published mix:

| Signature | Published | Share |
|---|---|---|
| along-track-raise | 816 | 54% |
| **inclination-change** | **441** | **29%** |
| along-track-lower | 135 | 9% |
| everything else | 108 | 7% |

Plane changes are among the most expensive manoeuvres in orbital mechanics.
Operators avoid them. **29% of published events being inclination changes is not
an operational pattern** — it is what a poorly conditioned channel looks like.
The inclination residual divides by `sin i`, which blows up near the equator.

Test against Phase 0's breakdown before touching anything. If the floor is
inclination-heavy, tighten that channel's conditioning and read the operating
point off the control curve rather than choosing it.

**Done when:** the floor falls without a proportional loss of payload catch. If
both fall together, revert — that is the symmetric trap.

## Phase 3 — the cohort lane: fix it or retire it

The cohort control measures a false-alarm rate of **26.5 per 1,000** and a
separation of **1.40x** — very nearly indistinguishable from noise.

Its window anchoring defect WAS fixed: it anchors on the capture ledger and
holds 41,301 intervals, against roughly 1,900 when the window was hours deep.
That repair worked and the lane is still not usable as a control.

It judges only ~57 of 1,500 published events, so almost no reader is affected.
But publishing a 1.4x control invites the belief that something was
corroborated.

**Done when:** it either clears a stated bar, or stops being presented as
corroboration.

---

## The guardrail that matters most

There is an easy way to reach 10x that would be worthless: keep trying changes
until the number crosses, then stop. That is fitting the detector to its own
acceptance test.

- **Pre-register each change.** State the mechanism and expected direction
  BEFORE measuring, in physics, not in parameters.
- **Measure on the control curve before enabling.** Ship disabled behind a flag
  with a failing test if it does not clear. Worked example already in the tree:
  the apse-line channel was built, measured, found to fire only on debris, and
  left switched off.
- **The threshold does not move to meet the data.** If we land at 9.2x, the
  answer is *not yet*, not "nine is fine".
- **Report what was dropped.** Any change that removes data reports the count,
  as the 2V ceiling guard does.

## Decisions

1. **The bar itself.** 10x is a JUDGEMENT, not physics. Argued from how much of
   the payload rate noise could account for, and deliberately not fitted — a
   threshold tuned to today's archive would have landed near 2x and passed on
   the spot. Sean agreed to keep 10x.
2. **The cohort lane.** Retire as a published control unless Phase 0 shows a
   cheap fix. A weak second opinion is worse than a declared single one.
3. **If 10x proves unreachable.** STILL OPEN. Decide while it costs nothing.
   Two respectable outcomes: keep saying *candidate* permanently, which is
   honest and still useful; or change what the site claims, naming causes at the
   population level while never labelling an individual event. What we must not
   do is quietly lower the bar.
