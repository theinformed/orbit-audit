/**
 * Loading the planner's two hand-authored datasets, and the vocabulary for
 * talking about time the way a ship does.
 *
 * The datasets are imported rather than fetched. They are small, they are part
 * of the build, and a planner that renders an empty capability list because a
 * second network request failed would be worse than one that cannot be built at
 * all. `resolveJsonModule` is already on in `tsconfig.json`.
 */

import capabilityData from "../data/satcom_capabilities.json";
import aorData from "../data/aor_reference.json";
import type { SatcomCapabilityDataset } from "./satcom-capabilities";

export const satcomCapabilities = capabilityData as unknown as SatcomCapabilityDataset;

export interface AorEntry {
  id: string;
  name: string;
  abbreviation?: string;
  statement: string;
  source: string;
  sourceName: string;
  archiveSource: string | null;
  drawable: boolean;
  drawabilityNote: string;
}

export interface AorReference {
  schema: 1;
  revised: string;
  boundaryOverlay: {
    headline: string;
    howItIsBuilt: string[];
    whatIsNotDrawn: string;
    regenerate: string;
  };
  combatantCommands: AorEntry[];
  numberedFleets: AorEntry[];
}

export const aorReference = aorData as unknown as AorReference;

// ---------------------------------------------------------------------------
// Time
// ---------------------------------------------------------------------------

/**
 * How a waypoint's clock time is entered and displayed.
 *
 * `zone` is included because it is what a ship actually keeps. Zone time is set
 * from longitude in fifteen-degree bands, so a waypoint's own local time depends
 * on where the waypoint is — which is exactly the quantity a planner is already
 * holding. Offering only "browser local time" would have meant a route across
 * the Pacific displayed in the time zone of whoever was looking at it.
 */
export type TimeConvention = "utc" | "zone" | "browser";

/**
 * Zone description for a longitude: the number of hours to ADD to zone time to
 * get UTC. West longitude is positive ZD, east is negative, in bands of fifteen
 * degrees centred on the standard meridians.
 *
 * The direction is the whole content of the definition, and this comment used
 * to have it backwards ("subtract from zone time to get UTC"). At 75 W the zone
 * description is +5 and zone time is UTC-5, so UTC = zone time + ZD.
 * `offsetMinutes` and `parseTime` below have always done it that way; only the
 * sentence was wrong.
 */
export function zoneDescription(longitudeDeg: number): number {
  const normalized = (((longitudeDeg + 180) % 360) + 360) % 360 - 180;
  // Round to nearest 15-degree band, then negate: 7.5 W to 7.5 E is ZD 0,
  // 172.5 E to 180 E is ZD -12.
  const zone = -Math.round(normalized / 15);
  return Math.max(-12, Math.min(12, zone));
}

/**
 * The military time-zone letter for a zone description.
 *
 * The table is indexed by UTC OFFSET, which runs OPPOSITE to the zone
 * description: ZD +5 is UTC-5, which is Romeo. So the index is 12 - ZD.
 *
 * CORRECTNESS FIX 2026-09-08. Two defects in four lines, neither reachable by
 * any test in the suite, both shipped, and both visible on the waypoint
 * readout whenever "Ship's zone time" was selected:
 *
 *  - THE SIGN WAS INVERTED, so every waypoint printed the letter for the
 *    opposite hemisphere. Tokyo Bay approaches (139.95 E, ZD -9, so UTC+9,
 *    which is India) printed "V", the letter for UTC-9. Pearl Harbor
 *    approaches (158.05 W, ZD +11, so UTC-11, which is X-ray) printed "M",
 *    the letter for UTC+12.
 *  - O WAS MISSING FROM THE TABLE. J is the one letter that is skipped, and
 *    the old comment said so correctly; O is not skipped - it is UTC-2 - and
 *    dropping it slid every letter west of Papa by a further hour.
 *
 * Both ends of the range exist: ZD +12 is UTC-12 (Yankee) and ZD -12 is UTC+12
 * (Mike), so the table is 25 letters long and the index runs 0 to 24.
 */
export function zoneLetter(zoneDescriptionHours: number): string {
  //               UTC-12                     UTC+0                    UTC+12
  const letters = "YXWVUTSRQPONZABCDEFGHIKLM";
  const index = 12 - zoneDescriptionHours;
  return letters[index] ?? "Z";
}

/** Offset from UTC in minutes for a convention at a given longitude and time. */
export function offsetMinutes(
  convention: TimeConvention,
  longitudeDeg: number,
  timeMs: number,
): number {
  if (convention === "utc") return 0;
  if (convention === "zone") return -zoneDescription(longitudeDeg) * 60;
  return -new Date(timeMs).getTimezoneOffset();
}

/** Format an instant in the chosen convention, always with its zone marked. */
export function formatTime(
  timeMs: number,
  convention: TimeConvention,
  longitudeDeg: number,
  withDate = true,
): string {
  const offset = offsetMinutes(convention, longitudeDeg, timeMs);
  const shifted = new Date(timeMs + offset * 60_000);
  const iso = shifted.toISOString();
  const clock = iso.slice(11, 16);
  const date = iso.slice(0, 10);
  let suffix: string;
  if (convention === "utc") suffix = "Z";
  else if (convention === "zone") suffix = zoneLetter(zoneDescription(longitudeDeg));
  else suffix = formatOffset(offset);
  return withDate ? `${date} ${clock}${suffix}` : `${clock}${suffix}`;
}

function formatOffset(minutes: number): string {
  const sign = minutes < 0 ? "-" : "+";
  const absolute = Math.abs(minutes);
  return `${sign}${String(Math.floor(absolute / 60)).padStart(2, "0")}${String(absolute % 60).padStart(2, "0")}`;
}

/**
 * Parse a datetime-local input value under a convention into UTC milliseconds.
 * Returns null for anything unparseable rather than a plausible wrong instant.
 */
export function parseTime(
  value: string,
  convention: TimeConvention,
  longitudeDeg: number,
): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(value.trim());
  if (!match) return null;
  const [, year, month, day, hour, minute] = match;
  const asUtc = Date.UTC(
    Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute),
  );
  if (!Number.isFinite(asUtc)) return null;
  if (convention === "utc") return asUtc;
  if (convention === "zone") return asUtc + zoneDescription(longitudeDeg) * 3_600_000;
  // Browser local: build a local Date so the platform applies its own rules,
  // including daylight saving, rather than assuming a fixed offset.
  const local = new Date(
    Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute),
  );
  return local.getTime();
}

/** The value a datetime-local input needs to show an instant in a convention. */
export function toInputValue(
  timeMs: number,
  convention: TimeConvention,
  longitudeDeg: number,
): string {
  if (convention === "browser") {
    const local = new Date(timeMs);
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`;
  }
  const offset = offsetMinutes(convention, longitudeDeg, timeMs);
  return new Date(timeMs + offset * 60_000).toISOString().slice(0, 16);
}

export function formatDuration(milliseconds: number): string {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "—";
  const totalMinutes = Math.round(milliseconds / 60_000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days} d ${hours} h`;
  if (hours > 0) return `${hours} h ${String(minutes).padStart(2, "0")} m`;
  return `${minutes} m`;
}
