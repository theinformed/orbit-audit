/**
 * TODAY'S CONSTELLATION: the pick, and the sentence the popup says about it.
 *
 * This file exists because two different readers need the same answer and only
 * one of them can load `main.ts`: the browser, and the Playwright specs, which
 * cannot import `main.ts` at all because its first line is `import
 * "./styles.css"`. A spec that hard-codes the name of today's constellation
 * expires at the next UTC midnight — two of them did, on 2026-08-21 — so the
 * rotation has to be importable on its own for a test to ask it the same
 * question the page asks it.
 *
 * The rotation itself moved here UNCHANGED on 2026-08-21. `main.ts` re-exports
 * every name below, so nothing that imported them from there had to move.
 *
 * IT HAS A PORT, AND THE PORT MUST NOT DRIFT.
 * `/root/apps/openclaw/space-featured-constellation.py` on the VPS reproduces
 * `featuredConstellation()` and `FEATURED_ANCHOR_DAY` exactly, so the daily
 * blurb is written about the fleet this file is going to pick. Change the
 * rotation here and change it there in the same commit; that script's
 * `self-test` pins ten days and fails loudly. Its own documentation names
 * `src/main.ts`, which still re-exports every one of these.
 */

/**
 * THE FEATURED CONSTELLATION. Sean: "We should be starting with a satellite or
 * constellation of the day. I say we start with GPS. Have that shown when you
 * load the page."
 *
 * It is expressed as a FACET SELECTION, not as a fourth kind of state, and
 * that is the whole design. The three facet boxes have to describe whatever is
 * drawn — that was the defect underneath every symptom this area produced — so
 * the feature goes through the same single source of truth every other
 * selection does: the constellation facet is ticked, healing grows mission and
 * owner to match, and the boxes read GPS / Navigation / U.S. Space Force
 * because that is genuinely the state, not because anything was hand-written.
 *
 * Nothing is stored and nothing is a favourite ("we wouldn't want it to be a
 * favorite or something like that"), and the ORBIT BAND is deliberately left
 * unset — showing GPS must not light MEO or All, because the reader applied
 * neither. Clearing it is clearing a facet: silent, and it leaves a bare globe
 * with nothing offering to bring it back.
 */
export const FEATURED_CONSTELLATIONS: readonly string[] = [
  "GPS",
  "Iridium",
  "Galileo",
  "GOES",
  "Sentinel",
  "GLONASS",
  "MUOS",
  "Starlink",
];

/** The UTC day GPS is the feature. Every other entry is that many days after
 *  it, so "GPS today" is a fact a test can pin rather than a coincidence of
 *  where the rotation happened to land. */
export const FEATURED_ANCHOR_DAY = Math.floor(Date.UTC(2026, 7, 20) / 86_400_000);

/** Whole days since the epoch, in UTC. Deterministic by date and the same for
 *  every visitor, so the feature is stable for a day and testable — which no
 *  `Math.random()` or `Date.now()` rotation would be. */
export function utcDayNumber(now: Date): number {
  return Math.floor(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) / 86_400_000);
}

export interface FeaturedConstellation {
  constellation: string;
  count: number;
  /** One line, with every number in it measured from the catalog rows
   *  themselves. It says nothing about operational status and nothing about
   *  the news, because the catalog publishes neither and this site does not
   *  invent either. */
  line: string;
}

/** Median rather than mean, so one drifting spare cannot move the altitude the
 *  line quotes. */
function medianOf(values: number[]): number {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)] ?? 0;
}

/**
 * Today's featured constellation, or null when the catalog carries none of the
 * rotation — in which case the site opens bare, which is a legitimate state and
 * needs no explaining.
 */
export function featuredConstellation(
  satellites: readonly {
    constellation: string | null;
    orbit: string;
    perigeeKm: number;
    apogeeKm: number;
  }[],
  dayNumber: number,
  rotation: readonly string[] = FEATURED_CONSTELLATIONS,
  anchorDay: number = FEATURED_ANCHOR_DAY,
): FeaturedConstellation | null {
  const stocked = rotation.filter((name) => satellites.some((satellite) => satellite.constellation === name));
  if (stocked.length === 0) return null;
  const offset = (((dayNumber - anchorDay) % stocked.length) + stocked.length) % stocked.length;
  const constellation = stocked[offset]!;
  const members = satellites.filter((satellite) => satellite.constellation === constellation);
  const bands = new Set(members.map((satellite) => satellite.orbit));
  const band = bands.size === 1 ? [...bands][0]! : null;
  const altitude = Math.round(medianOf(members.map((m) => (m.perigeeKm + m.apogeeKm) / 2)) / 100) * 100;
  const where = band ? `in ${band}, near ${altitude.toLocaleString()} km` : `near ${altitude.toLocaleString()} km`;
  return { constellation, count: members.length, line: `${members.length} ${constellation} spacecraft ${where}.` };
}

/** The UTC calendar day as the published blurb writes it, `YYYY-MM-DD`. */
export function utcIsoDay(now: Date): string {
  return now.toISOString().slice(0, 10);
}

/**
 * ONE DAILY BLURB, published beside the data release as
 * `data/featured-constellation.json` — deliberately next to `manifest.json`
 * rather than inside it or under `artifacts/`, which is what keeps the data
 * pruner and the publish gate off it.
 *
 * `kind` is the publisher's own word for how the text was made — its model
 * label when the local model wrote the second sentence, `"deterministic"`
 * when it did not —
 * and it is carried through to the page rather than assumed, because claiming
 * a machine wrote a sentence it did not write is a lie about provenance even
 * when every fact in the sentence is true.
 *
 * Every field is treated as untrusted here, because the file is written by a
 * different process on a different machine and may be absent, half-written, a
 * day old, or about a constellation the rotation is not showing. None of those
 * may put a wrong sentence on the page.
 */
export interface FeaturedBlurb {
  day: string;
  key: string;
  name: string;
  orbitClass: string;
  operator: string;
  text: string;
  kind: string;
  generatedAt: string;
}

/** The published `key` is a slug of the fleet name. Compared slug to slug, so
 *  `"O3b / mPOWER"` and `"o3b-mpower"` are the same fleet and a near miss is
 *  not. */
export function featuredKey(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** The catalog publishes a band code; these are the same fact in words. No
 *  band the catalog does not publish gets a name here, and an unrecognised
 *  code loses the clause rather than acquiring a guess. */
const ORBIT_CLASS_NAMES: Record<string, string> = {
  LEO: "Low Earth Orbit",
  MEO: "Medium Earth Orbit",
  GEO: "geostationary belt",
  IGSO: "inclined geosynchronous orbit",
  HEO: "highly elliptical orbit",
};

export interface FeaturedRow {
  constellation: string | null;
  orbit: string;
  perigeeKm: number;
  apogeeKm: number;
  organization?: string | null;
}

/**
 * THE SENTENCE THE SITE CAN ALWAYS SAY, because every clause in it is read off
 * the catalog rows for this fleet and off nothing else.
 *
 * The operator clause appears only when every member of the fleet carries the
 * SAME organization, and the orbit clause only when they all sit in one band
 * the catalog names. A fleet flown by three operators loses the clause rather
 * than having one of them picked for it, which is the difference between a
 * summary and an invention.
 */
export function featuredFallbackSentence(
  pick: FeaturedConstellation,
  satellites: readonly FeaturedRow[],
): string {
  const members = satellites.filter((satellite) => satellite.constellation === pick.constellation);
  const bands = new Set(members.map((satellite) => satellite.orbit));
  const operators = new Set(
    members.map((satellite) => satellite.organization ?? "").filter((name) => name.length > 0),
  );
  const bandName = bands.size === 1 ? ORBIT_CLASS_NAMES[[...bands][0]!] : undefined;
  const what = bandName ? `a ${bandName} constellation` : "a constellation";
  const who = operators.size === 1 ? ` operated by ${[...operators][0]}` : "";
  return `Showing the Satellite/Constellation of the day: ${pick.constellation}, ${what}${who}. ${pick.line}`;
}

/** A blurb longer than this is not a discreet popup, whatever it says. Past it
 *  the catalog sentence is used instead, because a toast that has to be
 *  scrolled is a panel nobody asked for. */
export const FEATURED_BLURB_MAX_CHARS = 600;

/**
 * WHAT THE POPUP SAYS. The model prose DECORATES; it never gates.
 *
 * The published blurb is used only when it is about the constellation today's
 * rotation actually picked, carries today's date, and is a sentence. Every
 * other case — missing file, malformed JSON, yesterday's file, a fleet the
 * rotation is not showing, an empty or absurd `text` — falls through to the
 * catalog sentence, which is always available and always true. There is no
 * state in which a failed fetch produces an empty or a wrong popup.
 */
export function featuredToastText(
  pick: FeaturedConstellation,
  satellites: readonly FeaturedRow[],
  blurb: unknown,
  todayIsoDay: string,
): { text: string; kind: string } {
  const fallback = { text: featuredFallbackSentence(pick, satellites), kind: "catalog" };
  if (blurb === null || typeof blurb !== "object") return fallback;
  const candidate = blurb as Partial<FeaturedBlurb>;
  if (typeof candidate.text !== "string") return fallback;
  const text = candidate.text.trim();
  if (text.length === 0 || text.length > FEATURED_BLURB_MAX_CHARS) return fallback;
  if (candidate.day !== todayIsoDay) return fallback;
  if (typeof candidate.key !== "string") return fallback;
  if (featuredKey(candidate.key) !== featuredKey(pick.constellation)) return fallback;
  // The publisher's own word for it, and "published" when it did not say —
  // never a model label by assumption.
  const kind = typeof candidate.kind === "string" && candidate.kind.trim().length > 0
    ? candidate.kind.trim()
    : "published";
  return { text, kind };
}
