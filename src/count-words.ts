/**
 * Small counts, spelled the way this site's prose spells them.
 *
 * Three door strings on the space-weather index were hand-written copies of
 * facts the data already held - the clip count, the mechanism library's
 * runtime, and the number of layer pages - and two of the three had gone stale
 * by the time anyone looked: the door said "6 min 32 s" against 7:12 of clips,
 * and "Ten pages" against eleven that render. Correcting a constant only moves
 * the next staleness to the next re-render, so the copy counts the array, and a
 * count that appears in prose rather than in a metadata line comes through
 * here.
 *
 * Kept in its own module because the two callers - src/content.ts and
 * src/mechanism-animations.ts - already import in the other direction, and one
 * word list in two files is how the counts diverged in the first place.
 */
const COUNT_WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
  "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
  "seventeen", "eighteen", "nineteen", "twenty",
];

/** "eleven". Falls back to the numeral above twenty, where prose would anyway. */
export function countWord(n: number): string {
  return COUNT_WORDS[n] ?? String(n);
}

/** "Eleven", for the head of a sentence. */
export function countWordCap(n: number): string {
  const word = countWord(n);
  return word.charAt(0).toUpperCase() + word.slice(1);
}
