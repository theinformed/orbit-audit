/**
 * Starred satellites — the visitor's own short list, kept on their machine.
 *
 * Three constraints shaped this module, and each one is a property the tests
 * pin rather than a preference:
 *
 * 1. **This browser only.** Part of this site's audience works on hardened
 *    government machines where an account is not something we may ask for and
 *    a server-side profile is not something we may keep. So the list lives in
 *    `localStorage` under one versioned key, nothing leaves the machine, and
 *    the section that shows it says so on screen.
 * 2. **Stable identifiers, never positions.** A favorite records the NORAD
 *    catalog number, which is the object's identity for its whole life. The
 *    catalog array is re-sorted, re-filtered and re-published every release,
 *    so an index would silently come to mean a different spacecraft; a name
 *    would collide (there are several "COSMOS 2251" fragments) and change
 *    (objects get renamed on transfer).
 * 3. **Corrupt storage degrades to empty, never to a crash.** Anything can be
 *    in that key: an older schema, a half-written value, another tab's data,
 *    or a browser that throws on read. Every one of those paths ends at an
 *    empty list and a working site.
 */

/** One versioned key. Bump the suffix, never the shape, if this ever changes. */
export const FAVORITES_STORAGE_KEY = "space-explorer-favorites-v1";

/**
 * The list is capped so a runaway click, a script, or years of use cannot grow
 * an unbounded blob in the visitor's browser storage, and so the rail section
 * stays a short list a person can read rather than a second catalog. Adding
 * past the cap is refused and said out loud — silently dropping the oldest
 * favorite would lose something the visitor chose to keep.
 */
export const MAX_FAVORITES = 200;

/** What is written to storage. `schema` lets a future reader recognise this. */
export interface FavoritesRecord {
  schema: 1;
  ids: number[];
}

export interface FavoritesChange {
  /** The list after the change; unchanged (same values) when nothing happened. */
  ids: number[];
  /** True when the id was added, false when it was removed or refused. */
  added: boolean;
  /** True when the add was refused because the list is already full. */
  capped: boolean;
}

/** A NORAD catalog number: a positive integer, and nothing else. */
function isCatalogNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

/**
 * Read whatever is in storage and return a clean list of NORAD numbers.
 *
 * Accepts the record shape this module writes and a bare array of numbers,
 * because a bare array is the obvious hand-edit and refusing it would be
 * pedantry. Everything else — null, `"undefined"`, truncated JSON, an object,
 * a list of names, numbers that are not catalog numbers — yields an empty
 * list. Duplicates are collapsed and the result is truncated to the cap, so a
 * hand-grown 10,000-entry file cannot make the rail unusable.
 */
export function parseFavorites(raw: string | null): number[] {
  if (typeof raw !== "string" || raw.length === 0) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  const candidate = Array.isArray(parsed)
    ? parsed
    : typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { ids?: unknown }).ids)
      ? (parsed as { ids: unknown[] }).ids
      : null;
  if (!candidate) return [];
  const clean: number[] = [];
  const seen = new Set<number>();
  for (const entry of candidate) {
    if (!isCatalogNumber(entry) || seen.has(entry)) continue;
    seen.add(entry);
    clean.push(entry);
    if (clean.length >= MAX_FAVORITES) break;
  }
  return clean;
}

/** The exact text written to the storage key. */
export function serializeFavorites(ids: number[]): string {
  const record: FavoritesRecord = { schema: 1, ids: ids.slice(0, MAX_FAVORITES) };
  return JSON.stringify(record);
}

export function isFavorite(ids: readonly number[], id: number): boolean {
  return ids.includes(id);
}

/**
 * Star or unstar one object. Removing always succeeds. Adding succeeds unless
 * the list is full, in which case the list is returned untouched with
 * `capped: true` so the caller can say why nothing happened.
 */
export function toggleFavorite(ids: readonly number[], id: number): FavoritesChange {
  if (!isCatalogNumber(id)) return { ids: [...ids], added: false, capped: false };
  if (ids.includes(id)) {
    return { ids: ids.filter((member) => member !== id), added: false, capped: false };
  }
  if (ids.length >= MAX_FAVORITES) return { ids: [...ids], added: false, capped: true };
  return { ids: [...ids, id], added: true, capped: false };
}

export interface FavoriteEntry {
  id: number;
  /** Position in the catalog array, or null when this release has no such object. */
  index: number | null;
  name: string;
  /** The two secondary lines of a row, in the same order a search result uses. */
  lines: [string, string];
  /** True when the object is not in the catalog this release published. */
  missing: boolean;
}

/** The minimum a catalog row must offer for a favorites row to be drawn. */
export interface FavoriteCatalogRow {
  id: number;
  name: string;
  orbit: string;
  organization: string;
}

/**
 * Turn stored ids into rows to draw.
 *
 * Objects the current catalog still carries sort by name, exactly as the
 * search results do. Objects it does not — decayed, deorbited, or dropped by
 * an upstream filter — are kept, listed last, and labelled: a favorite the
 * visitor chose is not something this site may quietly delete because a
 * release stopped publishing the row. They are drawn greyed and unclickable,
 * with the one honest reason we can give, and their own remove button.
 */
export function favoriteEntries(ids: readonly number[], catalog: readonly FavoriteCatalogRow[]): FavoriteEntry[] {
  const positions = new Map<number, number>();
  catalog.forEach((satellite, index) => {
    if (!positions.has(satellite.id)) positions.set(satellite.id, index);
  });
  const present: FavoriteEntry[] = [];
  const absent: FavoriteEntry[] = [];
  for (const id of ids) {
    const index = positions.get(id);
    if (index === undefined) {
      absent.push({
        id,
        index: null,
        name: `NORAD ${id}`,
        lines: ["Unavailable", "Not in this release's catalog — decayed, or no longer published."],
        missing: true,
      });
      continue;
    }
    const satellite = catalog[index]!;
    present.push({
      id,
      index,
      name: satellite.name,
      lines: [satellite.orbit, `NORAD ${satellite.id} · ${satellite.organization}`],
      missing: false,
    });
  }
  present.sort((left, right) => left.name.localeCompare(right.name) || left.id - right.id);
  absent.sort((left, right) => left.id - right.id);
  return [...present, ...absent];
}

/** "3 of 200 starred" — the visible count, written once so both callers agree. */
export function favoritesCountLabel(count: number): string {
  return `${count} of ${MAX_FAVORITES}`;
}
