/**
 * HOW THE OWNER LIST IS BROKEN UP, as pure functions over names and counts.
 *
 * 716 organizations is too many to read as one flat column, and Sean asked for
 * two independent ways to break it up — by how many spacecraft an owner flies,
 * and by first letter — either, neither, or both at once. The DOM work stays in
 * `main.ts`; the grouping decision lives here so it can be measured against the
 * real published catalog in a unit test rather than inferred from a screenshot.
 *
 * Nothing here selects, deselects or hides anything. Grouping is presentation:
 * the same rows, in a different arrangement. Toggling a sort must never change
 * which owners are ticked, and no function in this file is given the selection
 * to change.
 */

/**
 * THE COUNT BANDS, largest first, chosen against the real distribution rather
 * than out of the air. Measured on release 20260821T054618Z, 8,000 objects and
 * 716 organizations:
 *
 *     1000+     1 owner    (SpaceX, 4,664)
 *     500-999   0 owners
 *     100-499   4 owners
 *     50-99     6 owners
 *     25-49    14 owners
 *     10-24    34 owners
 *     5-9      62 owners
 *     2-4     187 owners
 *     1       408 owners
 *
 * Two rules shaped it. No band may hold most of the list — the largest here is
 * "exactly one spacecraft" at 408 of 716, 57%, and merging it with 2-4 would
 * have made one band of 83% that answers nothing. And no band may be dead
 * weight: `500-999` is empty TODAY, but it is the band a second mega
 * constellation lands in — OneWeb is already at 242 — so it is kept and simply
 * not drawn while it is empty. An empty band is never rendered, in any state.
 *
 * The counts banded are the ones ON THE ROWS, which are the counts inside the
 * live orbit band rather than the whole catalog. Anything else would file an
 * owner showing "(5)" under "100-499".
 */
export const OWNER_COUNT_BANDS: readonly { label: string; min: number; max: number }[] = [
  { label: "1000+", min: 1000, max: Number.POSITIVE_INFINITY },
  { label: "500–999", min: 500, max: 999 },
  { label: "100–499", min: 100, max: 499 },
  { label: "50–99", min: 50, max: 99 },
  { label: "25–49", min: 25, max: 49 },
  { label: "10–24", min: 10, max: 24 },
  { label: "5–9", min: 5, max: 9 },
  { label: "2–4", min: 2, max: 4 },
  { label: "1", min: 1, max: 1 },
];

/** The band label for a count, or null for a count no band covers — which is
 *  only zero, and a zero-count owner is not on offer in this band anyway. */
export function ownerCountBand(count: number): string | null {
  return OWNER_COUNT_BANDS.find((band) => count >= band.min && count <= band.max)?.label ?? null;
}

/**
 * A–Z, with anything that does not start with a Latin letter under `#`.
 *
 * Accents are folded first, so "Électricité" files under E rather than in a
 * bucket of one. The published catalog carries exactly one such name today;
 * a reader looking for it under E is right, and would never think to look
 * under a symbol.
 */
export function ownerInitial(name: string): string {
  const first = name.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().charAt(0);
  return first >= "A" && first <= "Z" ? first : "#";
}

export interface OwnerGroup {
  /** Stable across re-renders, so a reader's open folds survive a regroup. */
  key: string;
  label: string;
  /** Every owner in this group, flat, in this group's own order. Also what the
   *  header counts, so the header and the rows cannot disagree. */
  members: string[];
  /** Present only in the both-toggles-on shape: bands at the top level, A–Z
   *  inside each of them. */
  children?: OwnerGroup[];
}

/**
 * The owner list, grouped.
 *
 * `null` means "no grouping" — neither toggle is on, and the caller shows the
 * flat list it already had, untouched and in its existing order.
 *
 * Order is fully defined in every mode, because a list that reshuffles between
 * two identical states is unusable: bands descend by size; letters ascend with
 * `#` last; owners inside an alphabetical group are alphabetical; owners inside
 * a count band are count-descending, ties broken alphabetically.
 */
export function ownerGroups(
  order: readonly string[],
  counts: ReadonlyMap<string, number>,
  byCount: boolean,
  alphabetically: boolean,
): OwnerGroup[] | null {
  if (!byCount && !alphabetically) return null;
  const alpha = (names: readonly string[]) => [...names].sort((left, right) => left.localeCompare(right));
  const bySize = (names: readonly string[]) => [...names].sort(
    (left, right) => (counts.get(right) ?? 0) - (counts.get(left) ?? 0) || left.localeCompare(right),
  );
  const lettered = (names: readonly string[], prefix: string): OwnerGroup[] => {
    const buckets = new Map<string, string[]>();
    names.forEach((name) => {
      const key = ownerInitial(name);
      const bucket = buckets.get(key);
      if (bucket) bucket.push(name);
      else buckets.set(key, [name]);
    });
    return [...buckets.keys()]
      .sort((left, right) => (left === "#" ? 1 : right === "#" ? -1 : left.localeCompare(right)))
      .map((key) => ({ key: `${prefix}letter:${key}`, label: key, members: alpha(buckets.get(key)!) }));
  };
  if (!byCount) return lettered(order, "");
  return OWNER_COUNT_BANDS
    .map((band) => ({
      band,
      names: order.filter((name) => {
        const count = counts.get(name) ?? 0;
        return count >= band.min && count <= band.max;
      }),
    }))
    .filter((entry) => entry.names.length > 0)
    .map(({ band, names }) => (alphabetically
      ? {
        key: `band:${band.label}`,
        label: band.label,
        members: alpha(names),
        children: lettered(names, `band:${band.label}/`),
      }
      : { key: `band:${band.label}`, label: band.label, members: bySize(names) }));
}
