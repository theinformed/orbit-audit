/**
 * Export, for the gated build only.
 *
 * ## Why this is not available on the public site
 *
 * A document sheds its disclosure the moment it leaves the browser. The panel's
 * standing notice — fitted predictions, element age, line-of-sight geometry only
 * — is attached to the page, not to a CSV sitting in someone's downloads folder
 * three weeks later. On the public site the answer is therefore not exportable
 * at all, which is the only way to guarantee the caveat travels with it.
 *
 * Behind the gate the audience is different and the calculus changes: a reader
 * who signed in is a reader who can be told, in the file, exactly what they are
 * holding. So the rule here is that **every row carries its own provenance**, not
 * just the header. Somebody will paste one line of this into a message, and that
 * line has to survive the journey with its element epoch and its mask attached.
 *
 * That is why `EXPORT_PROVENANCE_LINE` lives in `src/transit-audience.ts` and is
 * read rather than retyped: a new format cannot be added without it.
 */

import {
  EXPORT_PROVENANCE_LINE,
  type AudienceProfile,
} from "./transit-audience";
import type { SatelliteVisibilityResult } from "./transit-solve";
import { formatDuration } from "./transit-planner-data";
import type { TransitRoute } from "./transit-route";
import { buildLegs } from "./transit-route";

export interface ExportContext {
  profile: AudienceProfile;
  route: TransitRoute;
  maskDeg: number;
  observerAltitudeKm: number;
  results: readonly SatelliteVisibilityResult[];
  /** Display name per satellite id, and the system it was matched to. */
  satelliteNames: ReadonlyMap<number, string>;
  systemBySatellite: ReadonlyMap<number, string>;
  catalogUpstreamAsOf: string;
  generatedAtMs: number;
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const iso = (timeMs: number) => new Date(timeMs).toISOString().replace(".000", "");

/**
 * The commented header block. Every exported file starts with this, and the
 * fields in it are the ones needed to reproduce or to challenge the numbers
 * below: the mask, the route, the catalog vintage, and the provenance line.
 */
export function exportHeaderLines(context: ExportContext): string[] {
  const legs = buildLegs(context.route);
  const totalHours = legs.reduce((sum, leg) => sum + leg.durationMs, 0) / 3_600_000;
  return [
    "# Transit SATCOM visibility windows",
    `# ${EXPORT_PROVENANCE_LINE}`,
    "#",
    `# Generated:            ${iso(context.generatedAtMs)}`,
    `# Elevation mask:       ${context.maskDeg.toFixed(1)} deg  <-- the assumption that most changes these numbers`,
    `# Observer height:      ${context.observerAltitudeKm.toFixed(3)} km above the WGS-84 ellipsoid`,
    `# Catalog upstream as of: ${context.catalogUpstreamAsOf}`,
    `# Route:                ${context.route.waypoints.length} waypoints, ${legs.length} legs, ${totalHours.toFixed(1)} h, ${context.route.trackModel}`,
    ...context.route.waypoints.map((waypoint, index) =>
      `#   WP${index + 1} ${waypoint.label}: ${waypoint.latitudeDeg.toFixed(4)} ${waypoint.longitudeDeg.toFixed(4)} @ ${iso(waypoint.timeMs)}`),
    "#",
    "# Element age is given per row. A window computed from two-week-old elements",
    "# is a far weaker claim than one computed from yesterday's, and nothing else",
    "# in this file distinguishes them.",
    "#",
  ];
}

const WINDOW_COLUMNS = [
  "satellite_id",
  "satellite_name",
  "system",
  "window_start_utc",
  "window_end_utc",
  "duration",
  "peak_elevation_deg",
  "peak_at_utc",
  "peak_range_km",
  "truncated_at_start",
  "truncated_at_end",
  "grid_step_s",
  "element_epoch_utc",
  "element_age_days_at_transit_end",
  "element_age_band",
  "elevation_mask_deg",
  "provenance",
] as const;

/**
 * One row per visibility window. `provenance`, `elevation_mask_deg` and the
 * element-age columns are repeated on every row on purpose — see the module
 * note: a single pasted line has to carry its own caveats.
 */
export function windowsToCsv(context: ExportContext): string {
  const rows: string[] = [
    ...exportHeaderLines(context),
    WINDOW_COLUMNS.join(","),
  ];
  for (const result of context.results) {
    for (const window of result.windows) {
      rows.push([
        result.satelliteId,
        context.satelliteNames.get(result.satelliteId) ?? `NORAD ${result.satelliteId}`,
        context.systemBySatellite.get(result.satelliteId) ?? "",
        iso(window.startMs),
        iso(window.endMs),
        formatDuration(window.endMs - window.startMs),
        window.peakElevationDeg.toFixed(2),
        iso(window.peakAtMs),
        Math.round(window.peakRangeKm),
        window.truncatedAtStart ? "yes" : "no",
        window.truncatedAtEnd ? "yes" : "no",
        result.gridStepSeconds,
        result.elementEpoch,
        result.elementAgeDaysAtEnd.toFixed(2),
        result.elementAgeBand,
        context.maskDeg.toFixed(1),
        EXPORT_PROVENANCE_LINE,
      ].map(csvCell).join(","));
    }
  }
  if (rows.length === exportHeaderLines(context).length + 1) {
    rows.push(`# No satellite reached ${context.maskDeg.toFixed(1)} deg elevation at any point on this route.`);
  }
  return rows.join("\n") + "\n";
}

/** Trigger a download. Kept separate so the CSV itself stays testable. */
export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function exportFilename(context: ExportContext): string {
  const start = new Date(context.route.waypoints[0]?.timeMs ?? context.generatedAtMs)
    .toISOString().slice(0, 10);
  return `transit-visibility-${start}-mask${context.maskDeg.toFixed(0)}deg.csv`;
}
