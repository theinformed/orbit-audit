/**
 * The planetary K index, seven days behind and three ahead.
 *
 * This is the most recognisable picture in operational space weather — the one
 * every forecaster and every Space Cadre briefing puts on a slide — and this
 * site has been ingesting all 81 three-hourly rows of it while drawing exactly
 * one number per day from them ("Highest 3-hour Kp"). The series was there the
 * whole time; nothing was plotting it.
 *
 * Kp is a quasi-logarithmic index of mid-latitude geomagnetic disturbance,
 * 0 to 9 in thirds, from a global network of magnetometers. NOAA maps its top
 * five values onto the G scale, and that mapping is the operational meaning:
 * G1 at Kp 5 through G5 at Kp 9.
 *
 * Three things this module refuses to do, all of them house rules:
 *
 * - **Observed, estimated and predicted never merge.** They are three
 *   different evidence classes on one axis, and the drawn bar says which it
 *   is. A forecast that looks like a measurement is the exact failure this
 *   site exists not to commit.
 * - **Gaps stay gaps.** A row with no value is absent, not zero — and zero is
 *   a real, common, meaningful Kp.
 * - **Nothing is interpolated.** The rows are three-hourly by construction;
 *   drawing a smooth line between them would invent sub-interval structure the
 *   index does not have. Bars, not a curve.
 *
 * ## The axes, rebuilt 2026-08-19
 *
 * Sean: "Something is wrong with the storm observed/forecast bar chart. The
 * axes are off." Three separate faults, all measured on the built page:
 *
 * 1. **There was no time axis at all.** A chart captioned "seven days behind,
 *    three ahead" carried not one date. `dayTicks` — eleven UTC midnights —
 *    was computed here and thrown away by the caller, and `nowIso` was
 *    accepted and explicitly `void`ed, so the reader could not find today.
 * 2. **The value axis was labelled only above Kp 5.** Every label was a G
 *    band, G1 through G5, and G1 begins at Kp 5 — the top 45% of the box. On
 *    a quiet week every drawn bar sat in the unlabelled 55% underneath, so
 *    the chart had a scale exactly where it had no data.
 * 3. **The axis type was a fixed 5 px inside a 320-unit viewBox that renders
 *    1,018 px wide.** Measured: 15.9 px at a 1440 viewport and 5.2 px at 390,
 *    from one declaration — a 3.1x swing, against 1.4x for every other chart
 *    on the page. The fix is to build the geometry at the container's own
 *    pixel width so one viewBox unit is one CSS pixel everywhere.
 *
 * And the colour: below-storm bars were cyan, and the two storm colours were
 * hex literals that happened to equal `--amber` and `--coral`. The board
 * directly above this chart already maps NOAA severity onto the site palette —
 * `--mint` at level 0, `--amber` at G1–G2, `--coral` at G3 and above — so the
 * bars now take those tokens and the two surfaces can no longer drift.
 */

/** NOAA's G scale, which starts at Kp 5. Below that there is no G level. */
export const KP_G_SCALE: ReadonlyArray<{ minimumKp: number; level: number; label: string }> = [
  { minimumKp: 9, level: 5, label: "G5 Extreme" },
  { minimumKp: 8, level: 4, label: "G4 Severe" },
  { minimumKp: 7, level: 3, label: "G3 Strong" },
  { minimumKp: 6, level: 2, label: "G2 Moderate" },
  { minimumKp: 5, level: 1, label: "G1 Minor" },
];

/** The G level of a Kp value, or 0 for "below storm level". */
export function kpStormLevel(kp: number | null): number {
  if (kp === null || !Number.isFinite(kp)) return 0;
  return KP_G_SCALE.find((band) => kp >= band.minimumKp)?.level ?? 0;
}

/** The operational label for a Kp value; null below G1, which is not a storm. */
export function kpStormLabel(kp: number | null): string | null {
  const level = kpStormLevel(kp);
  return level === 0 ? null : KP_G_SCALE.find((band) => band.level === level)!.label;
}

export type KpStatus = "observed" | "estimated" | "predicted";

export interface KpRow {
  time: string | null;
  kp: number | null;
  status: KpStatus | null;
}

export interface KpBar {
  /** Left edge and width in viewBox units. */
  x: number;
  width: number;
  /** Top edge and height; height is 0 for Kp 0, which must still be visible as a baseline tick. */
  y: number;
  height: number;
  kp: number;
  status: KpStatus;
  /** G level, 0 when below storm threshold. */
  level: number;
  timeIso: string;
}

/** One labelled row of the value axis: a Kp number left, its G band right. */
export interface KpValueTick {
  y: number;
  kp: number;
  /** G level this Kp opens, or 0 where the row is only a Kp reference. */
  level: number;
  /** `G1` … `G5`, or null below the storm threshold. */
  gLabel: string | null;
}

/** One UTC midnight on the time axis. */
export interface KpDayTick {
  x: number;
  iso: string;
  /** `12 Aug` at a month change or the first tick, `13` after that. */
  label: string;
  /** False when the tick is too close to the last labelled one to print. */
  labelled: boolean;
}

export interface KpChartGeometry {
  /** The box this geometry was built for; the caller sets the viewBox to it. */
  width: number;
  height: number;
  /** Plot rectangle inside the box, so the caller never re-derives padding. */
  plot: { left: number; right: number; top: number; bottom: number };
  bars: KpBar[];
  /** Rows of the value axis: Kp 0 and 3 for reference, then every G threshold. */
  valueTicks: KpValueTick[];
  /** x of the boundary between the last observed/estimated bar and the first predicted one. */
  forecastBoundaryX: number | null;
  /** x of the caller's clock, interpolated inside its three-hour slot, or null off-chart. */
  nowX: number | null;
  /** `21:37Z` — the label for that line. A time, so it is set as a readout. */
  nowLabel: string | null;
  /** Midnight ticks, for a day axis. */
  dayTicks: KpDayTick[];
  /** Rows that carried no usable value, reported rather than silently dropped. */
  skipped: number;
  maximumKp: number;
}

/**
 * Gutters, in CSS pixels, because the geometry is now built at the container's
 * own pixel width. Left holds one digit, right holds `G1`, bottom holds a date.
 */
const PADDING = { left: 24, right: 28, top: 14, bottom: 28 };
/** Matches `--fs-small` at the default interface scale; see `.now-kp-axis`. */
const AXIS_FONT = 11.6;
/** Kp rows that get a rule and a left-hand number but open no G band. */
const KP_REFERENCE_TICKS = [0, 3];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** `12 Aug` when the month is new or unknown, `13` when it is not. */
function dayLabel(time: number, previous: number | null): string {
  const date = new Date(time);
  const day = date.getUTCDate();
  if (previous === null) return `${day} ${MONTHS[date.getUTCMonth()]}`;
  return new Date(previous).getUTCMonth() === date.getUTCMonth()
    ? String(day)
    : `${day} ${MONTHS[date.getUTCMonth()]}`;
}

/**
 * Bar geometry for the Kp series.
 *
 * Time is laid out by INDEX rather than by clock, because the rows are a
 * regular three-hourly grid and index spacing keeps every bar the same width.
 * A missing row still consumes its slot, so a gap in the middle of the series
 * reads as a gap rather than closing up and shifting everything after it.
 *
 * `width` and `height` are the container's measured CSS pixels, so one unit of
 * the returned geometry is one rendered pixel and the axis type is the size it
 * was declared at on every viewport.
 */
export function kpChartGeometry(
  rows: readonly KpRow[],
  nowIso: string | null = null,
  width = 320,
  height = 132,
): KpChartGeometry {
  const usable = rows.filter((row) => row.time !== null);
  const plotWidth = Math.max(1, width - PADDING.left - PADDING.right);
  const plotHeight = Math.max(1, height - PADDING.top - PADDING.bottom);
  const left = PADDING.left;
  const right = left + plotWidth;
  const top = PADDING.top;
  const bottom = top + plotHeight;
  const slot = plotWidth / Math.max(1, usable.length);
  const barWidth = Math.max(1, slot * 0.82);
  // Kp is defined 0–9 and the axis is always the whole range: rescaling to the
  // observed maximum would make a quiet week look like a storm.
  const yOf = (kp: number) => top + plotHeight * (1 - Math.min(9, Math.max(0, kp)) / 9);

  const bars: KpBar[] = [];
  let skipped = 0;
  let maximumKp = 0;
  usable.forEach((row, index) => {
    if (row.kp === null || !Number.isFinite(row.kp) || row.status === null) {
      skipped += 1;
      return;
    }
    const barTop = yOf(row.kp);
    maximumKp = Math.max(maximumKp, row.kp);
    bars.push({
      x: left + index * slot + (slot - barWidth) / 2,
      width: barWidth,
      y: barTop,
      height: Math.max(0, bottom - barTop),
      kp: row.kp,
      status: row.status,
      level: kpStormLevel(row.kp),
      timeIso: row.time!,
    });
  });

  // The value axis. Two reference rows below the storm threshold, because
  // every bar in a quiet week lives there and the old axis labelled only the
  // empty half above G1; then one row per G band, numbered on the left and
  // named on the right.
  const valueTicks: KpValueTick[] = [
    ...KP_REFERENCE_TICKS.map((kp) => ({ y: yOf(kp), kp, level: 0, gLabel: null })),
    ...[...KP_G_SCALE]
      .sort((a, b) => a.minimumKp - b.minimumKp)
      .map((band) => ({
        y: yOf(band.minimumKp),
        kp: band.minimumKp,
        level: band.level,
        gLabel: band.label.split(" ")[0] ?? null,
      })),
  ].sort((a, b) => a.kp - b.kp);

  // Where measurement stops and forecast begins — the single most important
  // line on this chart, and the reason the two are never drawn alike.
  const firstPredicted = usable.findIndex((row) => row.status === "predicted");
  const forecastBoundaryX = firstPredicted >= 0 ? left + firstPredicted * slot : null;

  // The clock, interpolated inside its own three-hour slot. The forecast
  // boundary is a proxy for it and can sit up to one full period away: on the
  // release this was written against, the last measured period opened at
  // 21:00Z and the first forecast period at 00:00Z, so a boundary line drawn
  // as "now" was three hours late.
  const times = usable.map((row) => Date.parse(row.time!));
  const cadenceMs = times.length > 1 ? (times[times.length - 1]! - times[0]!) / (times.length - 1) : 3 * 3_600_000;
  const nowMs = nowIso === null ? Number.NaN : Date.parse(nowIso);
  let nowX: number | null = null;
  let nowLabel: string | null = null;
  if (Number.isFinite(nowMs) && times.length) {
    const offset = (nowMs - times[0]!) / cadenceMs;
    if (offset >= 0 && offset <= times.length) {
      nowX = left + offset * slot;
      nowLabel = `${new Date(nowMs).toISOString().slice(11, 16)}Z`;
    }
  }

  // A date every UTC midnight, and a printed date wherever there is room for
  // one. Below that spacing the tick still rules the plot; only the text goes.
  // `12 Aug` is six mono characters, about 3.6 em wide, plus a gap.
  const minimumLabelGap = AXIS_FONT * 5;
  const dayTicks: KpDayTick[] = [];
  let lastLabelledX = Number.NEGATIVE_INFINITY;
  let lastLabelledTime: number | null = null;
  usable.forEach((row, index) => {
    if (!row.time || row.time.slice(11, 16) !== "00:00") return;
    const x = left + index * slot;
    const time = Date.parse(row.time);
    const labelled = x - lastLabelledX >= minimumLabelGap;
    const label = dayLabel(time, labelled ? lastLabelledTime : null);
    if (labelled) {
      lastLabelledX = x;
      lastLabelledTime = time;
    }
    dayTicks.push({ x, iso: row.time, label, labelled });
  });

  return {
    width,
    height,
    plot: { left, right, top, bottom },
    bars,
    valueTicks,
    forecastBoundaryX,
    nowX,
    nowLabel,
    dayTicks,
    skipped,
    maximumKp,
  };
}

/**
 * One sentence stating what is on screen, for the chart's accessible label and
 * for the caption. Every chart on this site says its quantity, its window and
 * its range; a picture nobody can read the units of is decoration.
 */
export function kpChartSummary(rows: readonly KpRow[]): string {
  const values = rows.filter((row) => row.kp !== null).map((row) => row.kp as number);
  const observed = rows.filter((row) => row.status === "observed").length;
  const predicted = rows.filter((row) => row.status === "predicted").length;
  if (values.length === 0) return "No planetary K index rows are published in this release.";
  const peak = Math.max(...values);
  const storm = kpStormLabel(peak);
  return `Planetary K index, ${observed} observed and ${predicted} forecast three-hour periods. `
    + `Peak ${peak.toFixed(2)}${storm ? ` (${storm})` : " — below storm level"}.`;
}

/**
 * What this chart is and is not, shown beside it.
 *
 * It used to end with a sentence saying the forecast bars are a prediction and
 * are drawn differently for it. The chart now shades the forecast region and
 * outlines those bars, and the key names both, so the sentence was describing
 * a picture printed directly above it. Drawn beats written; it is gone.
 */
export const KP_LIMITATION =
  "Kp is a planetary average from a network of mid-latitude magnetometers, in three-hour periods. "
  + "It is not a local measurement and not an aurora forecast for any particular place: a high Kp "
  + "means the whole mid-latitude field is disturbed, not that anything is visible overhead.";
