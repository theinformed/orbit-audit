/**
 * Capability selection: "I need EHF SATCOM — what can I use, and for how much of
 * the transit?"
 *
 * ## Where the facts come from, and where they stop
 *
 * Two datasets, deliberately separate, owned by different files:
 *
 * 1. **`data/programme_participation.json`** — *which spacecraft carry which
 *    programme's payload.* Hosted payloads and shared missions, keyed by NORAD
 *    ID, each with the published statement that says so. It is not this module's
 *    file and this module does not write to it; it arrives already attached to
 *    each `SatelliteRecord.programmes[]` by the release pipeline. This is how
 *    GBS is resolved: GBS is a payload that rides on other programmes'
 *    spacecraft, so "which satellites provide GBS" is a hosted-payload question
 *    and is answered from that file rather than re-asserted here.
 *
 * 2. **`data/satcom_capabilities.json`** — *which service each programme
 *    publicly provides.* One row per system, each service carrying its own
 *    citation. This is the file this module owns.
 *
 * The split matters. Duplicating NORAD-to-programme attachment here would have
 * created a second, silently diverging copy of the hardest-won data on the site.
 *
 * ## The rule these tables are held to
 *
 * A capability appears only where a public source states it. Band is never
 * inferred from a spacecraft's name, its owner, its orbit, or the company that
 * built it. Where the public record says nothing, the row is absent, not empty
 * and not guessed — the same posture `docs/mission-speculation-design.md` takes
 * for mission inference, applied to radio spectrum.
 *
 * That posture has a visible cost, and the cost is the honest part: the planner
 * will show fewer options than a real communications plan would, because a real
 * plan draws on published *and* unpublished sources. It is a teaching tool for
 * the geometry of who can see you, using publicly documented systems as the
 * worked example. It is not a SATCOM access plan and cannot become one by
 * adding rows.
 *
 * ## What this module computes, and the boundary it stays inside
 *
 * It aggregates *published system-level* facts over *geometry*: this system
 * publicly provides this service; these catalogued spacecraft belong to that
 * system per the catalog's own source-backed `constellation` field; here is when
 * each was above your mask. That is arithmetic over published facts.
 *
 * It does not, and must not, work in the other direction — measuring the catalog
 * to discover that spacecraft belong together, or that an unnamed object serves
 * a programme. `docs/mission-speculation-design.md` section 1.6 excludes
 * object-to-object association outright, and the structural control there
 * applies here too: nothing below ever compares two spacecraft to each other.
 * Every satellite is matched to a system independently, by a field the upstream
 * catalog already carries.
 */

import type { SatelliteRecord } from "./types";
import { summarizeCoverage, type Interval, type CoverageSummary } from "./transit-visibility";

export type SourceKind = "us-government" | "allied-government" | "operator" | "prime-contractor";

export interface CapabilityNeed {
  needId: string;
  label: string;
  /** Short band description shown next to the label. */
  bandLabel: string;
  summary: string;
  /** Why a planner would pick this, in the site's teaching voice. */
  teachingNote: string;
}

export interface CapabilityService {
  needId: string;
  /** What the cited source actually says. Displayed with the citation, always. */
  statement: string;
  source: string;
  sourceName: string;
  sourceKind: SourceKind;
  /**
   * Internet Archive capture of the official page, where the live page refuses
   * automated requests. Most Department of Defense hosts do. Recording which
   * capture the quotation came from is what makes the claim re-checkable rather
   * than merely attributed.
   */
  archiveSource?: string;
}

/**
 * How a system's spacecraft are found in the catalog.
 *
 * `constellation` and `programmeId` both read fields the catalog already
 * carries from source-backed classification. `norad` is an explicit published
 * list. There is deliberately no "match by name pattern" and no "match by orbit"
 * — those would be inference dressed as lookup.
 */
export type SystemMatch =
  | { kind: "constellation"; constellation: string }
  | { kind: "programme"; programmeId: string }
  | { kind: "norad"; norad: number[] };

export interface SatcomSystem {
  systemId: string;
  name: string;
  abbreviation: string | null;
  sponsor: string;
  operator: string;
  orbitNote: string;
  status: "operational" | "partially-operational" | "ended" | "unstated";
  summary: string;
  match: SystemMatch;
  services: CapabilityService[];
  /** Anything the reader must know to read the row correctly. */
  caveat: string | null;
  /**
   * Present where the citation is an *older* official page because the current
   * one has had the fact removed.
   *
   * This happened repeatedly during research: band and host-satellite detail is
   * in the 2017 Air Force Space Command GBS fact sheet and absent from the
   * current Space Force one; "extremely high frequency (EHF)" is in the 2023
   * Milstar capture and gone from today's. Silently citing the older page would
   * hide that. Saying so is the difference between a citation and a claim.
   */
  supersededNote?: string;
}

export interface SatcomCapabilityDataset {
  schema: 1;
  revised: string;
  needs: CapabilityNeed[];
  systems: SatcomSystem[];
  /** Systems the public record could not support, listed so the gap is visible. */
  unsourced: Array<{ name: string; reason: string }>;
}

export interface ResolvedSystem {
  system: SatcomSystem;
  /** Catalog satellites matched to this system. May be empty; that is reported. */
  satellites: SatelliteRecord[];
}

/**
 * Attach catalog satellites to systems.
 *
 * Every satellite is tested against every system independently. No satellite is
 * ever compared to another satellite — see the module note above.
 */
export function resolveSystems(
  dataset: SatcomCapabilityDataset,
  satellites: readonly SatelliteRecord[],
): ResolvedSystem[] {
  return dataset.systems.map((system) => ({
    system,
    satellites: satellites.filter((record) => matchesSystem(record, system.match)),
  }));
}

export function matchesSystem(record: SatelliteRecord, match: SystemMatch): boolean {
  if (match.kind === "constellation") return record.constellation === match.constellation;
  if (match.kind === "norad") return match.norad.includes(record.id);
  return (record.programmes ?? []).some((participation) => participation.programmeId === match.programmeId);
}

export function systemsForNeed(resolved: readonly ResolvedSystem[], needId: string): ResolvedSystem[] {
  return resolved.filter((entry) => entry.system.services.some((service) => service.needId === needId));
}

export type CoverageVerdict =
  | "entire-transit"
  | "partial"
  | "none"
  | "not-computed";

export interface SystemCoverage {
  systemId: string;
  system: SatcomSystem;
  /** Catalogued spacecraft of this system that were actually solved. */
  solvedSatelliteIds: number[];
  /** Spacecraft matched in the catalog but excluded from the solve. */
  unsolvedSatelliteIds: number[];
  summary: CoverageSummary;
  verdict: CoverageVerdict;
  /** Per-satellite union, so the list can show which spacecraft did the work. */
  perSatellite: Array<{ satelliteId: number; summary: CoverageSummary }>;
}

/**
 * Coverage of the transit by each system: the union of its spacecraft's windows.
 *
 * "Covers the entire transit" is a union-then-complement, not an intersection of
 * per-satellite windows — a constellation covers you continuously when *some*
 * member is up at every instant, which is exactly the property a constellation
 * is designed for and exactly what a naive intersection would get wrong.
 */
export function summarizeSystemCoverage(
  resolved: readonly ResolvedSystem[],
  windowsBySatellite: ReadonlyMap<number, Interval[]>,
  startMs: number,
  endMs: number,
  /** Gaps at or below this are treated as a handover seam rather than an outage. */
  seamToleranceMs = 1000,
): SystemCoverage[] {
  return resolved.map((entry) => {
    const solvedSatelliteIds: number[] = [];
    const unsolvedSatelliteIds: number[] = [];
    const intervals: Interval[] = [];
    const perSatellite: SystemCoverage["perSatellite"] = [];

    for (const satellite of entry.satellites) {
      const windows = windowsBySatellite.get(satellite.id);
      if (!windows) {
        unsolvedSatelliteIds.push(satellite.id);
        continue;
      }
      solvedSatelliteIds.push(satellite.id);
      intervals.push(...windows);
      perSatellite.push({
        satelliteId: satellite.id,
        summary: summarizeCoverage(windows, startMs, endMs, seamToleranceMs),
      });
    }

    const summary = summarizeCoverage(intervals, startMs, endMs, seamToleranceMs);
    let verdict: CoverageVerdict;
    if (solvedSatelliteIds.length === 0) verdict = "not-computed";
    else if (summary.continuous) verdict = "entire-transit";
    else if (summary.coveredMs > 0) verdict = "partial";
    else verdict = "none";

    return {
      systemId: entry.system.systemId,
      system: entry.system,
      solvedSatelliteIds,
      unsolvedSatelliteIds,
      summary,
      verdict,
      perSatellite: perSatellite.sort((a, b) => b.summary.coveredMs - a.summary.coveredMs),
    };
  });
}

/**
 * Which systems are overhead at one instant — the waypoint-click interaction.
 *
 * Returns the set of system ids with at least one spacecraft above the mask at
 * `timeMs`. The planner dims every other row; it does not remove them, because
 * "this constellation exists and is not available to you here" is the answer to
 * the question, and hiding the row destroys it.
 */
export function systemsOverheadAt(
  resolved: readonly ResolvedSystem[],
  windowsBySatellite: ReadonlyMap<number, Interval[]>,
  timeMs: number,
): Set<string> {
  const overhead = new Set<string>();
  for (const entry of resolved) {
    for (const satellite of entry.satellites) {
      const windows = windowsBySatellite.get(satellite.id);
      if (!windows) continue;
      if (windows.some((window) => timeMs >= window.startMs && timeMs <= window.endMs)) {
        overhead.add(entry.system.systemId);
        break;
      }
    }
  }
  return overhead;
}

/** Satellites of a system above the mask at an instant, for the detail line. */
export function satellitesOverheadAt(
  entry: ResolvedSystem,
  windowsBySatellite: ReadonlyMap<number, Interval[]>,
  timeMs: number,
): number[] {
  return entry.satellites
    .filter((satellite) => (windowsBySatellite.get(satellite.id) ?? [])
      .some((window) => timeMs >= window.startMs && timeMs <= window.endMs))
    .map((satellite) => satellite.id);
}

/**
 * Validate the dataset's internal consistency. Called by the loader and by the
 * test suite, so a malformed row fails loudly rather than rendering as a blank.
 */
export function validateDataset(dataset: SatcomCapabilityDataset): string[] {
  const problems: string[] = [];
  const needIds = new Set(dataset.needs.map((need) => need.needId));
  if (needIds.size !== dataset.needs.length) problems.push("duplicate needId");
  const systemIds = new Set<string>();
  for (const system of dataset.systems) {
    if (systemIds.has(system.systemId)) problems.push(`duplicate systemId ${system.systemId}`);
    systemIds.add(system.systemId);
    if (system.services.length === 0) problems.push(`${system.systemId} has no services`);
    for (const service of system.services) {
      if (!needIds.has(service.needId)) {
        problems.push(`${system.systemId} references unknown need ${service.needId}`);
      }
      if (!/^https?:\/\//.test(service.source)) {
        problems.push(`${system.systemId}/${service.needId} has no usable source URL`);
      }
      // A plain-http citation is allowed only for a host that no longer exists,
      // and then only with the archive capture that proves what it said. Two
      // real cases: the 2017 Air Force Space Command GBS fact sheet and the U.S.
      // Army PEO C3T page, both long gone, both the last public statements of
      // GBS's band and hosts. Without the capture, an http URL is a dead link
      // dressed as evidence.
      if (service.source.startsWith("http://") && !service.archiveSource) {
        problems.push(
          `${system.systemId}/${service.needId} cites a plain-http URL with no archived capture`,
        );
      }
      if (service.statement.trim().length < 20) {
        problems.push(`${system.systemId}/${service.needId} statement is too short to be a claim`);
      }
    }
  }
  return problems;
}
