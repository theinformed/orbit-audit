import { describe, expect, it } from "vitest";

import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import {
  FAVORITES_STORAGE_KEY,
  MAX_FAVORITES,
  type FavoriteCatalogRow,
  favoriteEntries,
  favoritesCountLabel,
  isFavorite,
  parseFavorites,
  serializeFavorites,
  toggleFavorite,
} from "../src/favorites";

/**
 * Starred satellites: the visitor's own list, on the visitor's own machine.
 *
 * The properties worth testing here are the ones that break quietly. A
 * favorites list that loses its contents on a catalog re-publish, or that
 * throws on a half-written storage value and takes the whole page down with
 * it, fails weeks after it shipped and in someone else's browser. So each
 * test below is one of those failure modes, driven through the same functions
 * the application calls.
 */

/**
 * Storage, exactly as the site sees it: a string in, a string out. The real
 * `localStorage` is proven by the browser spec, which reloads the page; what
 * is proven here is that whatever we write is readable as what we meant.
 */
function fakeStorage() {
  const cells = new Map<string, string>();
  return {
    getItem: (key: string) => cells.get(key) ?? null,
    setItem: (key: string, value: string) => void cells.set(key, value),
    raw: cells,
  };
}

const catalog: FavoriteCatalogRow[] = [
  { id: 25544, name: "ISS (ZARYA)", orbit: "LEO", organization: "NASA" },
  { id: 20580, name: "HST", orbit: "LEO", organization: "NASA" },
  { id: 43226, name: "GOES 17", orbit: "GEO", organization: "NOAA" },
];

describe("what is written to this browser is what comes back", () => {
  it("round-trips a list through storage under the versioned key", () => {
    const storage = fakeStorage();
    const chosen = [25544, 43226, 20580];
    storage.setItem(FAVORITES_STORAGE_KEY, serializeFavorites(chosen));
    expect([...storage.raw.keys()]).toEqual(["space-explorer-favorites-v1"]);
    expect(parseFavorites(storage.getItem(FAVORITES_STORAGE_KEY))).toEqual(chosen);
  });

  it("stores catalog numbers, not names and not positions", () => {
    const stored = JSON.parse(serializeFavorites([25544])) as { schema: number; ids: unknown[] };
    expect(stored.schema).toBe(1);
    expect(stored.ids).toEqual([25544]);
    // If a name or an index ever leaked into the record, this is where it shows.
    expect(JSON.stringify(stored)).not.toContain("ISS");
  });

  it("survives a full toggle cycle without leaving residue", () => {
    const storage = fakeStorage();
    let ids = parseFavorites(storage.getItem(FAVORITES_STORAGE_KEY));
    expect(ids).toEqual([]);
    ids = toggleFavorite(ids, 25544).ids;
    storage.setItem(FAVORITES_STORAGE_KEY, serializeFavorites(ids));
    expect(isFavorite(parseFavorites(storage.getItem(FAVORITES_STORAGE_KEY)), 25544)).toBe(true);
    ids = toggleFavorite(ids, 25544).ids;
    storage.setItem(FAVORITES_STORAGE_KEY, serializeFavorites(ids));
    expect(parseFavorites(storage.getItem(FAVORITES_STORAGE_KEY))).toEqual([]);
  });
});

describe("corrupt storage degrades to an empty list, never to a crash", () => {
  const garbage: Array<[string, string | null]> = [
    ["nothing stored", null],
    ["an empty string", ""],
    ["truncated JSON", '{"schema":1,"ids":[25544'],
    ["the literal word undefined", "undefined"],
    ["a bare number", "7"],
    ["a string", '"25544"'],
    ["an object with no ids", '{"schema":1}'],
    ["ids that are not an array", '{"schema":1,"ids":"25544"}'],
    ["another feature's value", '{"profile":"quality","markerSize":"large"}'],
    ["null", "null"],
    ["a list of names", '["ISS (ZARYA)","HST"]'],
  ];
  for (const [description, raw] of garbage) {
    it(`reads ${description} as no favorites`, () => {
      expect(parseFavorites(raw)).toEqual([]);
    });
  }

  it("keeps the good entries out of a partly-bad list", () => {
    expect(parseFavorites('[25544,"HST",null,-3,1.5,0,43226,25544]')).toEqual([25544, 43226]);
  });

  it("accepts a bare array, which is the obvious hand edit", () => {
    expect(parseFavorites("[25544,20580]")).toEqual([25544, 20580]);
  });

  it("never lets a corrupt list produce a row that cannot be drawn", () => {
    const entries = favoriteEntries(parseFavorites('{"schema":1,"ids":[25544,"x"]}'), catalog);
    expect(entries).toHaveLength(1);
    expect(entries[0]!.name).toBe("ISS (ZARYA)");
  });
});

describe("a favorite is an identity, so the catalog can move underneath it", () => {
  it("finds the same spacecraft after the catalog is re-ordered", () => {
    const ids = [43226, 25544];
    const before = favoriteEntries(ids, catalog);
    const after = favoriteEntries(ids, [...catalog].reverse());
    expect(before.map((entry) => entry.name)).toEqual(after.map((entry) => entry.name));
    expect(before.map((entry) => entry.id)).toEqual(after.map((entry) => entry.id));
    // The positions differ — which is exactly why an index could not be stored.
    expect(before.map((entry) => entry.index)).not.toEqual(after.map((entry) => entry.index));
    expect(after.every((entry) => catalog[entry.index!]!.id === entry.id)).toBe(false);
    expect(after.every((entry) => [...catalog].reverse()[entry.index!]!.id === entry.id)).toBe(true);
  });

  it("resolves to the catalog row the id names, not the row at that number", () => {
    const [entry] = favoriteEntries([20580], catalog);
    expect(entry!.index).toBe(1);
    expect(entry!.lines).toEqual(["LEO", "NORAD 20580 · NASA"]);
  });

  it("lists present favorites by name, as the search results do", () => {
    expect(favoriteEntries([25544, 20580, 43226], catalog).map((entry) => entry.name))
      .toEqual(["GOES 17", "HST", "ISS (ZARYA)"]);
  });
});

describe("a favorite the catalog no longer carries is kept and labelled", () => {
  it("marks the missing object rather than dropping it", () => {
    const entries = favoriteEntries([25544, 99999], catalog);
    expect(entries).toHaveLength(2);
    const missing = entries.find((entry) => entry.id === 99999)!;
    expect(missing.missing).toBe(true);
    expect(missing.index).toBeNull();
    expect(missing.name).toBe("NORAD 99999");
    expect(missing.lines[1]).toContain("Not in this release's catalog");
  });

  it("puts missing objects last, so the usable list stays on top", () => {
    const entries = favoriteEntries([99999, 25544, 88888], catalog);
    expect(entries.map((entry) => entry.missing)).toEqual([false, true, true]);
  });

  it("does not disturb the rest of the list when every favorite is missing", () => {
    const entries = favoriteEntries([99999, 88888], catalog);
    expect(entries.every((entry) => entry.missing && entry.index === null)).toBe(true);
  });

  it("brings a favorite back on its own when the catalog carries it again", () => {
    const ids = [99999];
    expect(favoriteEntries(ids, catalog)[0]!.missing).toBe(true);
    const restored = [...catalog, { id: 99999, name: "RETURNED SAT", orbit: "MEO", organization: "USSF" }];
    expect(favoriteEntries(ids, restored)[0]!.missing).toBe(false);
    expect(favoriteEntries(ids, restored)[0]!.name).toBe("RETURNED SAT");
  });
});

describe("the list is capped, visibly", () => {
  const full = Array.from({ length: MAX_FAVORITES }, (_, index) => index + 1);

  it("caps at 200", () => {
    expect(MAX_FAVORITES).toBe(200);
    expect(full).toHaveLength(200);
  });

  it("refuses an add past the cap and says so, instead of silently doing nothing", () => {
    const change = toggleFavorite(full, 25544);
    expect(change.capped).toBe(true);
    expect(change.added).toBe(false);
    expect(change.ids).toEqual(full);
  });

  it("never drops an existing favorite to make room", () => {
    expect(toggleFavorite(full, 25544).ids).toContain(full[0]);
    expect(toggleFavorite(full, 25544).ids).toHaveLength(MAX_FAVORITES);
  });

  it("still removes when full, which is how the visitor gets unstuck", () => {
    const change = toggleFavorite(full, full[0]!);
    expect(change.capped).toBe(false);
    expect(change.ids).toHaveLength(MAX_FAVORITES - 1);
    expect(toggleFavorite(change.ids, 25544).capped).toBe(false);
  });

  it("truncates an over-long stored list rather than loading all of it", () => {
    const oversized = JSON.stringify({ schema: 1, ids: Array.from({ length: 5_000 }, (_, index) => index + 1) });
    expect(parseFavorites(oversized)).toHaveLength(MAX_FAVORITES);
  });

  it("writes at most the cap back to storage", () => {
    const stored = JSON.parse(serializeFavorites([...full, 900001])) as { ids: number[] };
    expect(stored.ids).toHaveLength(MAX_FAVORITES);
  });

  it("states the count against the cap", () => {
    expect(favoritesCountLabel(0)).toBe("0 of 200");
    expect(favoritesCountLabel(3)).toBe("3 of 200");
  });
});

/**
 * The bottleneck check. Six features on this project were built, tested and
 * reachable from nothing, because every feature's last two lines land in
 * index.html and main.ts. These assert those two lines exist.
 */
describe("the feature is wired into the page, not merely written", () => {
  it("imports the favorites module from the entry point", () => {
    expect(explorerSource).toMatch(/from "\.\/favorites"/);
  });

  it("mounts a favorites section in the satellites panel of the rail", () => {
    // `data-rail-panel` is what puts a section in one rail rather than the
    // other now — the two doors on a phone and the two tabs on a desktop both
    // read it, and the stylesheet draws only the sections that carry the open
    // rail's value. It is asserted separately from the class because the
    // section carries a `data-mode-panel` of its own between the two.
    expect(indexMarkup).toMatch(/class="rail-section favorites-section"[^>]*data-rail-panel="satellites"/);
    expect(indexMarkup).toContain('id="favorites-list"');
    expect(indexMarkup).toContain('id="favorites-count"');
  });

  it("puts a star on the satellite card itself", () => {
    expect(indexMarkup).toContain("data-card-favorite");
    expect(indexMarkup).toMatch(/class="favorite-star"/);
  });

  it("says where the list lives, once, where the list lives", () => {
    const matches = indexMarkup.match(/Stored only in this browser/g) ?? [];
    expect(matches).toHaveLength(1);
  });

  it("reads and writes the one versioned key", () => {
    expect(explorerSource).toContain("FAVORITES_STORAGE_KEY");
    expect(explorerSource).not.toContain('"space-explorer-favorites');
  });
});
