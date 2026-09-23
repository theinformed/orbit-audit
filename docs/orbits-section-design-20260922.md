# Orbit changes: a new top-rail section — DESIGN ONLY

> **STATUS: DESIGN. No code, no route, no artifact, no timer exists for any
> of this.** Written 2026-09-22 for the implementing session. It is bound by
> `docs/alarm-lane-design-20260922.md` (§1, §5–§8, §10) and the T8a/T8b/T8d
> results it quotes; where the two disagree, the alarm design wins.

**The operator's brief, verbatim:** *"design a portion of our site where we
have some sort of way to show satellites that have made a maneuvre or some
sort of change, and we can sort of show how the orbit was and will be, and
then show what satellites it will likely affect… it would be cool if we could
have a warning system for that… the main website should be the satellite and
space weather viewer. But then on the rail at the top there should be another
portion of the site dedicated to orbit history and maneuvres and early warning."*

---

## 0. Decisions needed from the operator (alarm design §10)

§10.1 is now decided: **a public surface exists** (this section).

**ANSWERED 2026-09-22, and the answers are what the build follows, not the
recommendations beside them.** 10.4 **yes**; 10.6 **live in v1, not post hoc**;
10.3 **still open**. The answered rows carry their answer in bold at the head of
the Recommendation column, and where an answer departs from the recommendation
the reason he gave is recorded with it. The remaining rows are recommendations
with their reasons, and the build should not start an affected view until the
row is answered.

| § | Decision | Recommendation | Why |
|---|---|---|---|
| 10.2 | Framing | **A public record of orbit changes, in the site's existing teaching-and-research voice.** Not "situational awareness". The page states its departure from named-actor narratives in one sentence in its *What this is not* block. | Keeps the section inside the site's family and on the right side of the military line (§4). |
| 10.3 | Registry codes | **STILL OPEN (he asked why).** Until it is answered the section holds the narrow behaviour: never on an alert, a reach list, a filter or an aggregate, and only as the same one-line registry metadata the Explorer's satellite card already prints for that object, on the object page. No country filter or aggregate is built speculatively against the answer. | The instrument reads none; a country filter would manufacture the per-nation narrative §7.3 forbids. Answering the row means adding a surface with its own review, not turning one on. |
| 10.4 | Names | **ANSWERED YES — catalogue names as facts**, beside the NORAD number. Held behind `SHOW_CATALOGUE_NAMES` in `src/orbit-changes-policy.ts` so a reversal stays one line. | The main viewer already names every object; a numbers-only page would be less legible, not more careful. |
| 10.5 | Notification | **No** in v1. The page is pull-only; nothing leaves the machine. Revisit after one month of live ledger. | An outbound feed is a different product with its own retention and audience questions. |
| 10.6 | LEO arm | **ANSWERED LIVE IN v1 — this overrides the recommendation.** The LEO arm is built as a live lane on the same ledger contract as the GEO arm, labelled *in-track phasing campaigns* everywhere it appears, carrying its own measured numbers (median lead 195.9 d, 44.1% over 161 archive alerts, control zero events in 18.79 M object-days) and never the GEO arm's. **Plane matching remains absent and is not a setting**: no candidate set built by matching one object's plane to another's, in either direction. His reason: traffic is low today and he wants the surface ready for the v2/v3 data rather than waiting behind it. | The recommendation was *not live*, on T8b §2.3: plane channel blinded, plane-noise floor not yet re-derived. That constraint is discharged by building the phase lane and no plane product, rather than by withholding the whole arm. |
| 10.7 | Retention | **Keep the ledger forever; publish the running precision.** The ledger stays on `pc`; the site carries every spoken alert and its resolution. | Deleting rows is the silent suppression §7.9 bans; the running figure is the audit. |

---

## 1. Placement

**Today's top bar** (`index.html` `<nav class="topnav">`, eight entries, hash
router in `src/main.ts::openContent`): Explorer · Current conditions ·
Historical events · Satellite fundamentals · How it works · Learn space
weather · Connections · Transit visibility. A ninth was removed on 2026-08-21
because the bar was "getting too crowded", so this addition is the operator's
own call, and it should be the only one.

| | Proposal |
|---|---|
| Label | **Orbit changes** (mobile label **Changes**; "Orbits" is already taken by Satellite fundamentals) |
| Route | `#/orbits` — sub-routes `#/orbits/timeline`, `#/orbits/object/<norad>`, `#/orbits/event/<eventKey>`, `#/orbits/reach/<alertId>`, `#/orbits/alerts` |
| Position | after *Historical events*, before the Learn entries — it is a record, not a lesson |
| Why not "Manoeuvres" | the shipped bundle's `manoeuvreLabelPermitted` is **false** (34 flags in 1,941 passive intervals); a rail label may not use a word the detector has not earned |
| Why not "Early warning" / "Watch" | the warning view is one of four; the words read as a product the section is not (§4) |

The main viewer is untouched: no chip, no badge, no count on the Explorer.
Wiring is three edits (button in `index.html`, a branch in `openContent()`,
`state.page` handling in `openTrackPage()`); no build-config change.

**Traffic roster:** no new row. This is a section of `/space/` served by the
same container (`space-teaching-aid-web-1`, `SITE_ROSTER` id `space`), so its
page loads land in the log that row already reads. The row's `gapNote` covers
only `orbit-history-*` shards proxied from bigmem; every artifact this section
adds (§6) is published to the VPS by `publish_vps.sh` and is therefore counted.

---

## 2. The four views, and what each can truthfully show

### 2.1 Timeline — "made a manoeuvre or some change"

A browsable, filterable list of **element changes**, newest first, from two
families of record the site already holds or has committed:

| Family | Source | Rows | What a row says |
|---|---|---|---|
| Catalogue changes | `manifest.orbitEvents` bundle (`MAX_HEADLINE_EVENTS = 1500`, refreshed ~daily by `orbit-release`) | 1,500 | signature label (17 kinds: in-plane raise/lower, inclination change, node change, GEO east-west / north-south keeping, drag decay, …), regime, the element change itself (Δa km, Δi °, Δḋ °/day), confidence — always *candidate* |
| Slot co-locations, GEO | `docs/proximity-events-20260922.jsonl` (T8a, frozen, 771 KB) | 487 | arrival within 0.1° of another object's mean longitude, held ≥ 30 d; loiter, transfer drift rate, flag present or not |
| Co-orbital stations, LEO | `docs/proximity-leo-events-20260922.jsonl` (T8b, frozen, 5.1 MB — slimmed at release) | 71 | plane agreement ≤ 0.2°, phase inside ±5°, ≥ 30 d; **labelled "in-track phasing campaign"** on every row |
| Live triggers | alarm-lane ledger (§3) | grows | confirmed drift-rate change, class, spoken or withheld |

Filters: regime (LEO / MEO / GEO / HEO), family, signature kind, date range,
object search. **No filter by country or registry code** (§0, 10.3). The
frozen families print their archive end date ("archive to 22 Sep 2026") in
the list header; when they are re-measured (v2) the date moves.

Vocabulary on this view: "orbit change", "drift-rate change", the signature
labels, "slot co-location", "co-orbital station". Never "manoeuvre" (withheld
bundle-wide), never "approach" per row (T8a §7.4, T8b §12.4).

### 2.2 Object page — "how the orbit was and will be"

One object, one shared time axis, the event marked. Two regimes, two
renderings, because the physics is different:

**GEO / near-GEO — the longitude strip.** Mean longitude λ against time (the
slot coordinate T8a defines: λ = Ω + ω + M − GMST). Left of the event: the
observed series from the element sets (daily, 180 d). Right of the event: the
observed series where it exists, and beyond the newest element set the
**forward path** — the J22 resonance integration the alarm lane already uses
(`dλ/dt = ḋ`, `dḋ/dt = −K sin 2(λ − 75.1°)`, K = 1.70e-3 °/day², RK4, 1-day
step; a straight line is wrong by ½KH² = 6.9° at 90 d and 27.5° at 180 d).
Occupied longitudes of stationed objects are drawn as faint horizontal bands
so the reader sees what the path crosses.

**LEO / MEO / HEO — the element small multiples** the orbit-history browser
already draws (perigee/apogee band, detrended semi-major axis in metres,
inclination, eccentricity), reused as a module, plus for a T8b event the
**relative phase** to the partner object.

**The honest uncertainty, derived, not assumed:**

| Regime | Element noise alone | Measured forward error | What to draw |
|---|---|---|---|
| GEO | σ_ḋ = 6.04e-4 °/day (T8a §2.2) → 0.018° at 30 d, 0.11° at 180 d | at +30 d, median **0.408°**, p75 0.898°, p95 2.08° (T8d Gate W, n = 49,318) — 22× the noise floor: the error is what the object *does next* (its own station-keeping, a second burn), not what the elements cannot measure | ribbon at the measured p50/p75/p95 to +30 d; **beyond 30 d, hatched and labelled "error not measured beyond 30 days"**; the path itself drawn to the class p95 (90 d for class 1) and no further |
| LEO | σ_n = 6.27e-5 rev/day median (T8b §2.2) → along-track **0.023°/day ≈ 2.7 km/day** at 500 km; p95 objects 5.4e-3 rev/day → 233 km/day, phase lost in days | none measured for this site | draw the median growth as a ribbon **only on the phase panel**, print the p95 as a sentence; no propagated ground track, no "position on day N" |

What the forward path can claim: *where the mean longitude would be if the
object did nothing further.* What it cannot claim: position, miss distance,
what the operator will do, anything at all past the measured horizon. Both
sentences are printed under the chart, not linked.

### 2.3 Reach — "what satellites it will likely affect"

**Not a target prediction. A reachable set.** For a spoken GEO alert (class 1
only, §3), the belt is drawn as a 360° strip; the forward path sweeps an arc
from the object's longitude at the observed post-change drift rate; every
**stationed** object (|ḋ| ≤ 0.020 °/day, the lane's own eligibility proxy)
whose mean longitude lies inside the swept arc ± 0.1° is a **candidate**,
listed in order of days-to-reach, with the arc drawn to the class p95
(90.0 d) and the measured +30 d error band on the sweep edge.

Printed beside the list, verbatim from the lane's vocabulary:

> Of 822 confirmed drift changes matching this pattern, 28 ended within 0.1°
> of *any* satellite's mean longitude for 30 days or more — 3.4%, Wilson 95%
> 2.4–4.9%. **That figure is for any satellite. No figure exists for a
> particular one.** Base rate for a drift change of any kind: 0.10%.

So a list of k candidates is exactly that: the k objects the drift can reach
in the window. The precision is not divided among them and nothing is ranked
by "likelihood".

**LEO — REVISED by the operator's 10.6 answer, 2026-09-22.** The arm is live in
v1, on the same ledger contract as the belt arm, and it carries its own
measured numbers: a 195.9-day median lead at 44.1% over the archive's 161
alerts, against a control that returned zero events in 18.79 M object-days.
Every row it draws is labelled an **in-track phasing campaign**, because that
is the population those numbers were measured on: T8b proved the lead for
**in-track phasing inside an already-shared plane** and nothing else.

**Plane matching stays absent, and it is not a setting.** The plane channel was
blinded (T8b §2.3) and its noise floor has not been re-derived, so there is no
candidate set built by matching one object's plane to another's, in either
direction, and no sentence claiming one. What the LEO arm shows is phase inside
a plane two objects already share — the partner, the phase series, the closure
— plus, for a live ledger row, the same alert card the belt arm draws. Until
the lane writes its ledger, the LEO alert list renders the same labelled gap
the belt arm does; the historical campaigns render from the frozen record
either way.

### 2.4 Alerts — the warning

A list of every **spoken** alert from the lane's ledger, newest first, each
rendered from the lane's own `text` and `vocabulary` fields and nothing else
(§3). Below it, the month's accounting as counts: triggers assessed, withheld
(class 0), not assessable, alerts raised, resolved / expired / pending, and
the running precision `k/n` of this lane against the frozen 3.41%.

---

## 3. What the alarm lane feeds the page, and how the page renders the gate

The lane (`tools/alarm_lane.py`, being built; design §2.2) is a read-only
sidecar with its own timer, state file and ledger. **The page is a consumer of
the ledger and never a second detector**: it computes no trigger, assigns no
class, quotes no precision the ledger did not carry.

| Ledger field (JSONL, `runtime/alarm-lane/alarm-lane-ledger.jsonl`) | Page use |
|---|---|
| `spoken`, `assessable`, `class`, `className` | only `spoken = true` rows become alerts; `assessable = false` rows are counted as **"not assessable"** — never zero, never blank |
| `text` | rendered verbatim as the alert body; the page composes no sentence about an alert |
| `vocabulary.permitted`, `.labels`, `.underpowered`, `.mayRaiseAlert` | the page shows a field only if its clause id is in `permitted`; `labels` (NOT ASSESSABLE / UNDERPOWERED / NOT AN ALERT) are printed as stamps in the site's `.layer-status` style |
| `classPrecision`, `classWilson95`, `classSupport`, `classPositives`, `populationPrecision` | printed beside every alert, both figures, labelled which is which |
| `classArrivalDays` {p5…p95} | the lead-time clause as a range (p25–p75) with the median — never a point |
| `driftChangeDegPerDay`, `tTrigIso`, `tAnnounceIso`, `resolveByMs` | the facts line and the expiry |
| `resolution.state` | pending / resolved / expired; an expired alert stays on the page as a miss |
| `modelVersion`, `modelChecksum` | footer of every alert: the precision names the model that earned it |

The two structural caveats (design §5.4) are printed on the face of every
alert and on the Reach view: *mean longitude is a slot coordinate, not a miss
distance — this is not a conjunction warning*; *the catalogue is a lower
bound — absence of an alert is not evidence of absence.*

**The page has no vocabulary of its own.** Its string table for the Alerts and
Reach views is generated at release time from the frozen model's clause words
and `neverSay` list, and a unit test asserts that no user-facing string in the
section contains a `neverSay` term or the words *manoeuvre*, *approach*,
*threat*, *inspect*, *hostile*, *adversary*, *shadow*, *stalk*, *intent*,
*purpose*, *fuel*, *first*, *validated* — the union of prior-art forbidden
phrasings and design §7.

### 3.5 The certainty dial (operator input, 2026-09-22)

The operator's words: *"You're giving me a lot of candidates but what if we
wanted something a bit more certain? We could pre-compute different intervals…
I don't mind burning computational power on pre-computing multiple sets of
data for different tuning settings."*

**Principle, in the honest register: the dial changes which alerts are shown,
not how certain any single alert is.** Every alert at every setting carries
its own class precision, and the vocabulary gate applies at every setting.

**(1) Operating-point curve, precomputed on the historical replay.** The lane's
replay machinery runs the frozen detector over the archive once per setting
of five evidence thresholds and records, per pattern class, the whole
trade-off row — nothing is fitted, only counted:

| Threshold axis | Values swept | What tightening costs |
|---|---|---|
| class membership | class 1 only / any class | recall |
| drift magnitude \|Δḋ\| | floor 0.010 °/day and up, ~6 steps | recall |
| persistence over N sweeps | 1…4 consecutive element sets beyond confirmation | **lead**: each sweep ≈ 0.87 d of a 22 d median (near-GEO epoch spacing) |
| reachable-set size | ≤ 1, ≤ 3, ≤ 10, any candidates within the horizon | recall; a small set is a *quieter* alert, not a surer one |
| lead horizon | 30 / 60 / 90 / 180 d | which arrivals count |

Row = {setting, n triggers, positives, precision + Wilson 95%, median lead
and p25–p75, alerts/yr (2010s pro-rated, labelled arithmetic), recall proxy
= share of the 101 flagged arrivals retained, UNDERPOWERED flag if n < 20}.
The whole table is versioned with the frozen model (`modelVersion`,
`modelChecksum`); a new model means a new table. Compute is CPU-only and
small (T8d's full primary arm ran on CPU; T8c's did in 144 s) — no GPU.

**Measured today — the curve has exactly two points**, and the page may show
no others until the replay has produced them:

| Setting | precision | median lead | alerts/yr (2010s) | recall proxy |
|---|---:|---:|---:|---:|
| everything (any confirmed drift change) | 0.103% [0.085, 0.125] | 25.7 d | ≈ 7,200 | 101/101 |
| class 1 | 3.41% [2.37, 4.88] | 22.1 d | ≈ 25–30 | 28/101 |

**(2) The dial.** A segmented control with a small fixed set of precomputed
stops — *everything · balanced · high-confidence · very high* — never a
slider. Each stop is a label **and its three measured numbers beside it**
(precision, median lead, alerts per year), read from the table; a stop whose
row is UNDERPOWERED (n < 20) is not offered. The default stop is the one the
lane speaks unaided (class 1). *Everything* shows withheld class-0 rows as
individual cards only if the operator so decides; the recommendation is
that it shows them as the count it shows today, because a card at 0.075% is
"a labelled gap dressed as a result" (alarm design §6).

**(3) The reach view shrinks as the dial tightens**, and the page says so in
one line under the strip: *"Tighter settings show fewer candidates and give
later warning."* Fewer candidates because the reachable-set cap and the
shorter horizon remove them; later because persistence waits for more element
sets. The candidate list never re-orders by "likelihood" at any stop.

**(4) Data contract addition.** The lane emits
`alarm-lane-operating-points-<modelVersion>.json` (the table above, one row
per setting × class, with provenance and checksum) at `freeze` time; the
release step (§6) publishes it as `orbit-alert-settings-<sha>` (≈ 10 KB gz).
The `orbit-alerts` artifact carries, per alert, the evidence values the stops
filter on (class, |Δḋ|, persistence count, reachable-set size, horizon), so
the page's filter is arithmetic on ledger fields; **the page never computes
a precision** — every figure it prints comes from the operating-points
artifact or the ledger row.

---

## 4. Naming, framing, and where the line is

Standing constraints, regardless of §0: no intent language; no per-nation
narrative authored by us (catalogue names and public registry lines are facts;
our prose is facts plus match); no velocity-change, propellant, mass or
remaining-life figure anywhere in this section (the Explorer's existing
inference card is out of scope and unchanged); nothing that reads as a
military product.

**Where the line is, plainly.** A military product answers *who is doing what
to whom and why*. This section answers *which public element sets changed,
by how much, what the same arithmetic has done before, and how often that
ended in co-location*. Concretely, the section must never have: a watchlist
of operators or countries; an "activity" feed grouped by flag; a red/amber
hazard palette on alerts (the site's `--coral`/`--amber` are space-weather
severity colours and stay there); a per-object dossier ("this object has done
this N times" — gate H fired, and §7.11 forbids it even where it is true);
any sentence with a subject other than an object's elements or a count over
the catalogue. The page's *What this is not* block says: *"Ownership-agnostic
arithmetic on public element sets. It attributes no purpose to anyone. It is
not a conjunction service and does not replace one."* — the framing departure
the prior-art review licenses stating, and nothing more.

---

## 5. Design plan

**Theme: dark only.** The site has one theme (`:root { color-scheme: dark }`;
styles.css states the second theme is not implemented). The section honours
that and adds none — a light theme would be a site-wide token decision, not
this section's. Nothing new is written as a literal colour; every value below
is an existing `:root` token or a section-scoped alias of one. (The existing
`orbit-history.css` aliases `--text-primary` etc. that do not exist in `:root`
and silently fall back — do not copy that pattern; alias real tokens.)

| Role | Token | Use here |
|---|---|---|
| ground | `--void` / `--surface` / `--surface-2` | page, panels, chart plates |
| text ramp | `--text` / `--muted` / `--type-body-color` | the seven type roles unchanged: KICKER (mono, tracked, names a surface only), TITLE, LABEL, SECTION, BODY, READOUT (mono, measurements only), ANSWER |
| accent | `--cyan` / `--cyan-bright` | the *after* orbit, live readouts, the swept arc fill at .22 alpha |
| before | `--muted` at .6 | the *was* orbit / series |
| change kinds | alias `--oc-change: var(--amber)`, `--oc-plane: var(--violet)`, `--oc-drift: var(--mint)`, `--oc-drag`: the orbit-history blue | timeline markers and legend — one legend for the whole section |
| gap | `--muted` hatch, `--line` hairline | "not measured", "not assessable", archive offline |
| hairline | `--line` / `--line-strong` | axes, table rules, panel borders |
| spacing | `--space-1…5` | 4-px grid |

**Layout.** One column, max 1120 px, 16-px gutters on phones; the section
header carries a segmented control for the four views (Timeline · Object ·
Reach · Alerts). Timeline: a dense table (date · object · regime · change ·
size · family · stamp) with a sticky filter row; rows open the object page.
Object page: kicker (surface name), title (object), a facts line
(NORAD · regime · last element set), then the strip or small multiples, then
the event card, then the uncertainty sentences. Reach: strip on top, candidate
table below, precision block beside. Alerts: cards, the lane's text, precision
block, stamps, footer.

**Information design (each item is a real rendering, not decoration):**

| View | Rendering | Machinery |
|---|---|---|
| Timeline | dense table + a 2-D density strip above it (events per week, per regime) with a brush that sets the date filter | new 2-D (SVG) |
| Longitude strip (GEO) | λ–t chart, event marker, observed series, forward path, measured error ribbon to +30 d then hatched, occupied-longitude bands | new 2-D (SVG or canvas) |
| Small multiples (LEO) | perigee/apogee band, Δa metres, inclination, eccentricity; partner phase panel | reuse `orbit-history-browser` modules |
| Reach strip | 360° belt as a horizontal strip, stationed objects as ticks, swept arc, candidates highlighted, hover names the object | new 2-D (SVG) |
| Alert card | text, facts line, precision pair, stamps, expiry | HTML |
| "Show in Explorer" | deep link that opens the main viewer focused on the object; **v1 draws nothing new on the globe** | existing focus route |

**WebGL.** v1 adds no shader, no texture, no offscreen pass, so no WebGL gate
is owed. A v1.1 candidate — a *before* ring on the globe beside the live one,
via `orbit-polyline` — must ship behind a URL flag with the offline GLES
harness run on any new shader string and the operator told the publish has
WebGL in it, per the estate rule. Browser captures (`npm run test:browser`,
desktop / tablet / mobile projects) are the pixel gate for the 2-D views.

**Formatting laws:** longitude 2 decimals with E/W, drift 3 decimals °/day,
days as integers, precision 1 decimal with its interval, dates "22 Sep 2026";
no ISO timestamps, no JSON, no raw floats; zero and none render as a labelled
gap or not at all; methodology words only inside a *Details* disclosure.

**No machine-phrased prose in v1.** Every string is code-rendered from the
frozen vocabulary or the catalogue's own signature prose.

---

## 6. Data contract and cost

**Reads (existing):** `manifest.orbitEvents` (3.3 MB gz, already fetched on
first open of the orbit-history dialog); `orbitPlotViews` per-object small
views; `orbit-history-NNN` shards via the bigmem proxy for the LEO small
multiples (the `ARCHIVE_OFFLINE` fifth state is inherited, not re-invented).

**New artifacts — one new release step, CPU only, seconds, no GPU.** A
`pipeline/orbit_changes_release.py` that runs at the tail of `orbit-release`
(or on its own daily timer if the tail budget is tight), reads the archive
read-only (`mode=ro`, `PRAGMA query_only`), the frozen event files and the
lane's ledger, and writes content-addressed artifacts through the existing
`write_fragment()` path so `orbit_release.publish` merges them into the
manifest as `orbitChanges`. `publish_vps.sh` then rsyncs them within 5
minutes like every other artifact.

| Artifact | Contents | Size (browser) | Refresh |
|---|---|---|---|
| `orbit-changes-index-<sha>` | slim timeline rows for all four families (last 3 years; older on demand) | ≈ 250 KB gz | daily with `orbit-release` |
| `geo-belt-<sha>` | every near-GEO object: NORAD, name, λ, ḋ, stationed flag, last epoch | ≈ 60 KB gz (1,768 rows) | daily |
| `orbit-changes-event-<norad>-<key>-<sha>` | per event: λ series ±180 d (GEO) or phase series (LEO), forward path, error band, partner | 2–6 KB each, fetched on open | daily for pending alerts; once for frozen events |
| `orbit-alerts-<sha>` | every spoken ledger row (fields of §3) plus the evidence values the dial filters on, monthly counts, running precision, model version | ≈ 30 KB gz first year | every lane firing (daily) |
| `orbit-alert-settings-<sha>` | the operating-point table of §3.5, from the lane's `alarm-lane-operating-points-<modelVersion>.json` | ≈ 10 KB gz | once per frozen model |

Landing view budget: shell + index + belt ≈ **320 KB gz**; an object page
adds one event file; a LEO object page adds one 3.3 MB gz shard from bigmem
(existing behaviour, existing offline state). No new GPU consumer: nothing
here touches a card. If the LEO arm or a monthly re-measure of the T8a/T8b
catalogues is ever added, that is a separate lane with its own registration
and cost line, and this document does not authorise it.

Dependencies on the lane: the Alerts and Reach views cannot render until the
lane's timer is installed (design §2.2), which the lane's own build owes with
its replay exercised first (`tools/alarm_lane_replay.py`, 2010–2019 window,
in sample). Until then those two views render the labelled gap *"The alert
lane is not yet running"* — the section can ship with Timeline and Object
first.

---

## 7. Build plan (ordered; each step has a check)

Out of scope for v1: any globe drawing; **plane matching in either direction**
(the live LEO arm is in scope per the answered 10.6, its plane product is not);
re-measuring the T8a/T8b catalogues; notification; country/registry filters (10.3
is open and nothing is built against the answer); a light theme; any change to
the Explorer's satellite card.

| # | Step | Verify by |
|---|---|---|
| 1 | Operator answers §0 rows 10.3, 10.4, 10.6 (the others can wait) | written answer in this file's header |
| 2 | Section string table + `neverSay` test (`tests/orbit-changes-vocabulary.test.ts`) generated from the frozen model | test asserts the bug first (a seeded forbidden word fails), then passes |
| 3 | `orbit_changes_release.py`: index + belt + event files; unit tests on a fixture archive | artifacts byte-stable across two runs on the same input; sizes within §6 |
| 4 | Manifest fragment merged as `orbitChanges`; `publish_vps.sh` unchanged | manifest on the VPS names the new artifacts; `deploy/publish_data.py` hashes pass |
| 5 | Route + rail entry + section shell (`src/orbit-changes.ts`, `src/orbit-changes.css` using aliased root tokens) | `npm run check`, `npm test`; `#/orbits` resolves at all three breakpoints |
| 6 | Timeline view with filters and density strip | browser captures desktop/tablet/mobile; release-review greps (px fonts, ad-hoc rgba, long decimals, ALL-CAPS, jargon) return nothing |
| 7 | Object page: GEO longitude strip with the RK4 path and measured ribbon; LEO small multiples reuse | a test reproduces T8d's stable points (75.1°, −104.7°) from the browser integrator; the ribbon stops at +30 d |
| 8 | Alerts view from a **synthetic ledger** produced by the replay tool with an injected clock — exercised now, not on tonight's run | every replay row renders; withheld rows appear only as counts; precision pair printed on every card |
| 8b | Operating-point table from the replay (lane build emits it); dial stops wired to it | every stop's three numbers match the table row; an UNDERPOWERED row is not offered; the page contains no precision arithmetic (grep) |
| 9 | Reach view for a replay class-1 alert against the belt file, at each dial stop | candidate count equals an independent computation on the same files; the "any satellite" sentence present; the list shrinks monotonically as the dial tightens |
| 10 | Pixel review of every capture against the site's own pages by the conductor before publish | captures attached to the change report |
| 11 | Deploy per `docs/DEVELOPER-HANDOFF.md#release-procedure`: gates on bigmem, `dist/` built with `--outDir` outside the repo (never `npm run build`), mutation claim, keep `dist-pre-<commit>-<UTC>`, rebuild/recreate only `web`, verify asset names and manifest, desktop+phone smoke, change report, release the claim | container healthy, restart count 0, public HTML names the new bundle |
| 12 | Lane timer installed by the lane's own build; Alerts/Reach leave the labelled-gap state | first live ledger line rendered on the public page |

Each pipeline step is run now with a fixture; nothing waits for a scheduled
firing to prove itself.

---

## 8. Is early warning possible?

**Yes, narrowly, and the page must show the narrowness.** At GEO the measured
median causal lead is 36.1 days (p25–p75 10.6–96.0 d) for the two thirds of
487 co-locations that had a confirmable initiating drift change; but at
trigger time — the only moment a warning can be issued — a confirmed drift
change is routine station-keeping (about 7,200 a year across the belt in the
2010s), and the whole-population precision is 0.103% (101 of 97,784). One
reproducible class speaks: 3.41% (Wilson 2.37–4.88%, 28 of 822, 45× lift),
with a median 22.1 days of warning (p25–p75 7.0–47.5 d). In a typical recent
month a reader would see **about two alerts**, each naming a reachable set of
a few stationed objects and each carrying "3.4% of changes like this ended in
co-location with any satellite"; roughly **one alert a year** resolves as a
co-location and the rest expire on the page as misses, counted. Below the
alerts, some 600 assessed drift changes a month appear only as a number,
withheld. Turning the certainty dial tighter shows fewer of those two alerts
with fewer candidates and a shorter lead; it does not make any one of them
more certain, and the tighter stops have no measured numbers until the
replay produces them. At LEO the 195.9-day median lead (44.1% precision, 161 alerts over
the whole archive) is real but is the lead of an in-track phasing campaign
inside a shared plane — mostly constellation members — and no live LEO arm
exists until the plane-noise floor is re-derived. What the page cannot do: say
which satellite (the precision is for any), say why (no purpose is attributed),
say a miss distance or a collision risk (mean longitude is a slot coordinate),
speak about an object's own past (gate H fired), or claim that silence means
nothing is happening — 33% of the co-locations had no visible initiating
flag. Aggregate finding, printed once on the section's front: GEO relocations
end near another satellite 2.2× *less* often than chance.

---

## 9. Sources of every number

```
docs/alarm-lane-design-20260922.md          §1, §2.2–2.3, §4, §5.1–5.4, §6, §7, §8, §10
docs/trigger-alarm-results-20260922.md      §0, §3.1–3.4, §4, §5.3–5.4, §8
docs/proximity-results-20260922.md          §1.1, §2.2, §3.2, §4, §4.1, §6, §7.4
docs/proximity-leo-results-20260922.md      §1.1, §2.2–2.3, §3.3, §4, §4.1–4.3, §9, §12
docs/proximity-priorart-20260922.md         Forbidden phrasings
docs/alarm-lane-model-20260922.json         detector constants, classes, neverSay
docs/orbit-history-design.md §2             element-set noise floor (787 triples)
pipeline/orbit_release.py, orbit_events.py  MAX_HEADLINE_EVENTS, SIGNATURES, _label_policy
tools/alarm_lane.py                         ledger schema, permitted_vocabulary()
index.html, src/main.ts, src/styles.css     rail, router, tokens
RUNBOOK.md, docs/DEVELOPER-HANDOFF.md       build and release procedure
```
Derived here and labelled as such: 0.018°/0.11° (σ_ḋ × H); 6.9°/27.5°
(½KH²); 2.7 km/day and 233 km/day (360·σ_n·r); "about two a month" and
"600 a month" (pro-rated from T8d §3.1's decade table, arithmetic not
measurement).
