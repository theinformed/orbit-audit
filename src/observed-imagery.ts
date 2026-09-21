import { evidenceBadge } from "./learning-evidence";
/**
 * Observed solar imagery, and one labelled illustration, for the historical events.
 *
 * WHY THIS EXISTS
 * ---------------
 * (2026-08-21: the page carries six events, and the two that this module held
 * NOTHING for -- `bastille-2000` and `stpatricks-2015`, for which
 * `observedImageryBlock` returned the empty string and the reader saw no frame
 * and no sentence explaining the absence -- now carry harvested footage of
 * their own dates. Sean: "some don't have any media.")
 *
 * Three of the four events on this page had no picture at all. `eventSchematicBody`
 * says so in as many words — "nothing here is drawn as data" — because the schematic
 * that used to sit there could not tell two events apart. That sentence is still true
 * and still printed: this module does not add a replay and does not animate any
 * measurement of the storm.
 *
 * What it adds is the thing the site was missing and could have had for free the whole
 * time: REAL, DATED, PUBLIC-DOMAIN INSTRUMENT FOOTAGE of the Sun on the days these
 * events began. A LASCO C3 loop of the actual 8 May 2024 CME is both more convincing
 * and more honest than any drawing of a CME could be.
 *
 * PROVENANCE IS IN THE PIXELS
 * ---------------------------
 * Every frame is rendered by the Helioviewer Project (NASA GSFC / ESA), which burns the
 * instrument name and the UTC timestamp of each contributing layer into the frame
 * itself. Where a clip composites three instruments it prints three separate times,
 * because they were taken at three separate moments. That is exactly the rule in
 * SCIENTIFIC-LAYERS.md — co-displayed observations do not acquire a common analysis
 * time by sharing a frame — and here it is enforced by the source rather than by us.
 *
 * THE TWO EVIDENCE CLASSES NEVER SHARE A FRAME
 * --------------------------------------------
 * `observed` clips and the single `illustration` clip are separate <figure> elements
 * with separate badges, separate colours and a hard rule between them. Nothing
 * generated is ever composited into, or cut together with, instrument footage.
 *
 * QUÉBEC 1989 DELIBERATELY HAS NO CLIP
 * ------------------------------------
 * Not an omission. SOHO's archive starts in 1996 and SDO's in 2010, so no space-based
 * solar observatory existed in March 1989. The absence is the teaching point and is
 * rendered as prose, not as a gap.
 */

import "./observed-imagery.css";

const asset = (file: string) => new URL(`../media/${file}`, import.meta.url).href;
// Vite resolves `new URL(...)` asset globs one directory level at a time, so
// narration needs its own helper. Without it the mp3 URLs point at files that were
// never emitted into the bundle, and the audio fails silently in production.
const narrationAsset = (file: string) =>
  new URL(`../media/narration/${file}`, import.meta.url).href;

/**
 * WHY NO EVENT CLIP CARRIES A VOICE PLAYER ANY MORE.
 *
 * Sean, 2026-08-26, on the St Patrick's event: "there is only one video that has my voice
 * and it is weird. It is a video you can play by itself and a short audio file where I talk.
 * I think we can remove my voice from that. It is oddly placed." Then Bastille Day, then
 * Halloween, then the general rule: "basically all the audio with my voice except the quebec
 * blackout are like 10 second audio clips that sort of are weirdly placed."
 *
 * He is describing a real defect and naming its cause exactly. Each of these was a single
 * 9-14 s render bolted ALONGSIDE a silent video - it has no relationship to the clip's
 * timeline, it starts wherever the reader presses it, and it says things about a picture
 * that is not moving while it says them. It reads as a stray element because that is what
 * it is.
 *
 * The Québec mechanism clip is the counter-example and the pattern to copy: its lines are
 * TIMED against the animation's own clock (`media/quebec-1989-gic-chain.marks.json`, seven
 * beats emitted by tools/emit_marks.py) and muxed into the video, so the voice belongs to
 * the picture. Sean: "The quebec video is AMAZING." A future treatment of these seven lines
 * needs marks of that kind, not a file played beside the frame.
 *
 * NOTHING WAS DELETED. The renders stay at media/narration/<stem>.mp3, their words stay in
 * media/narration/manifest.json and narration/script.json, and the pronunciation lane still
 * covers them. They are paid ElevenLabs renders in Sean's cloned voice, loudness-matched at
 * -16.5 to -17.4 LUFS; nobody should re-render them.
 *
 * EVERY SPOKEN WORD IS STILL WRITTEN DOWN. Where a line was the only place a fact appeared
 * anywhere on the page - the Gannon transit speed, the size of active region 13664, SOHO's
 * design life - that fact is now in the caption under the picture, in prose, where a reader
 * who cannot hear, has the sound off, or reads faster than anyone talks will find it.
 *
 * `narrationBlock` is kept for `absence`, which is the one place a voice is not standing
 * beside a picture it is out of step with: there is no picture there at all.
 */
import narrationManifest from "../media/narration/manifest.json";

const NARRATION_TEXT = new Map<string, string>(
  (narrationManifest.lines as Array<{ id: string; text: string }>).map((l) => [l.id, l.text]),
);

function narrationBlock(stem: string | undefined): string {
  if (!stem) return "";
  const src = narrationAsset(`${stem}.mp3`);
  const said = NARRATION_TEXT.get(stem);
  return `
      <audio class="oi-audio" preload="none" controls src="${src}" aria-label="Narration"></audio>
      ${said ? `<details class="oi-transcript"><summary>What the narration says</summary><p>${escapeHtml(said)}</p></details>` : ""}`;
}

type EvidenceClass = "observed" | "illustration";

interface MediaClip {
  /** File stem under media/ — expects `<stem>.mp4` and `<stem>.jpg`. */
  stem: string;
  evidence: EvidenceClass;
  /** The stamp. Tracked caps, WORD · WORD idiom, names the instrument and the date. */
  badge: string;
  heading: string;
  /** What the picture does not say for itself. */
  caption: string;
  /** Shown in the disclosure. Where the frames came from and what was done to them. */
  provenance: string;
}

interface EventMedia {
  clips: MediaClip[];
  /** Rendered instead of clips when no instrument existed. */
  absence?: { heading: string; caption: string; narration?: string };
}

const HELIOVIEWER =
  "Frames rendered by the Helioviewer Project (NASA Goddard Space Flight Center / ESA) " +
  "from the mission archives. Re-encoded for the web; no frame was retouched, " +
  "recoloured or reordered. The instrument name and UTC time in each frame are burned " +
  "in by Helioviewer, not added here.";

export const EVENT_MEDIA: Record<string, EventMedia> = {
  "gannon-2024": {
    clips: [
      {
        stem: "gannon-2024-cme",
        evidence: "observed",
        badge: "LASCO C2/C3 + AIA 304 · OBSERVED 2024-05-08/09",
        heading: "The cloud that did it, leaving the Sun",
        caption:
          "Two days before the storm. The black disc is the coronagraph's occulter, " +
          "holding back the Sun so the faint corona around it can be seen at all. " +
          "Each frame prints three times because three instruments contributed to it. " +
          "The cloud escaping past the mask crossed a hundred and fifty million kilometres " +
          "in about two days, and was still moving near a thousand kilometres a second when " +
          "it reached us.",
        provenance: HELIOVIEWER,
      },
      {
        stem: "gannon-2024-region",
        evidence: "observed",
        badge: "SDO AIA 193 Å · OBSERVED 2024-05-08 → 05-10",
        heading: "Active region 13664, three days before impact",
        caption:
          "The knot of bright loops near the centre is one active region, about fifteen " +
          "Earth diameters across. It is the region that produced the 14 May X8.7 flare, " +
          "carried across the disc by the Sun's rotation while it fired off flare after " +
          "flare for a week.",
        provenance: HELIOVIEWER,
      },
    ],
  },

  "halloween-2003": {
    clips: [
      {
        stem: "halloween-2003-cme",
        evidence: "observed",
        badge: "SOHO EIT 195 + LASCO C2/C3 · OBSERVED 2003-10-28",
        heading: "28 October 2003, the day of the X17",
        caption:
          "SDO would not launch for another seven years. Everything here is SOHO, " +
          "almost eight years into a two-year design life when it recorded this — " +
          "and still returning coronagraph frames today.",
        provenance: HELIOVIEWER,
      },
    ],
  },

  "starlink-2022": {
    clips: [
      {
        stem: "starlink-2022-sun",
        evidence: "observed",
        badge: "SDO AIA 193 Å · OBSERVED 2022-01-29 → 02-03",
        heading: "The five days before the launch",
        caption:
          "This is what an unremarkable Sun looks like. The geomagnetic storm that " +
          "followed was minor, and it was still enough to raise the air at 200 km " +
          "and take the launch down.",
        provenance: HELIOVIEWER,
      },
      {
        stem: "thermosphere-descent",
        evidence: "illustration",
        badge: "Generated illustration · not a measurement",
        heading: "What thicker air actually means, drawn",
        caption:
          "A stylised descent through a thickening medium. There is no altitude where " +
          "the air stops and space begins — it only ever gets thinner, and a satellite " +
          "in low orbit flies through it rather than above it.",
        provenance:
          "Machine-generated from a text prompt (Runway gen4.5) and deliberately drawn " +
          "in a flat silkscreen style so it can never be mistaken for a photograph or a " +
          "measurement. No number in it was measured, computed or modelled: the particle " +
          "spacing is illustrative and carries no density scale. It depicts no real date, " +
          "no real orbit and no real spacecraft. It is shown here because the misconception " +
          "it addresses — that satellites fly above the atmosphere — is the one this site " +
          "has fought hardest, and a diagram of a boundary tends to reinforce the very " +
          "boundary that does not exist.",
      },
    ],
  },

  "bastille-2000": {
    clips: [
      {
        stem: "bastille-2000-cme",
        evidence: "observed",
        badge: "SOHO EIT 195 + LASCO C2/C3 · OBSERVED 2000-07-14",
        heading: "The instrument being hit by the storm it was recording",
        caption:
          "The white speckle that fills the frame partway through is not noise in the " +
          "recording and not an artefact of this harvest. It is protons from this event " +
          "striking the coronagraph's detector, arriving at the spacecraft within the hour " +
          "of the flare. SOHO sits upstream of the Earth, so the picture degrades before " +
          "anything reaches the ground.",
        provenance: HELIOVIEWER,
      },
    ],
  },

  "stpatricks-2015": {
    clips: [
      {
        stem: "stpatricks-2015-cme",
        evidence: "observed",
        badge: "SDO AIA 304 + SOHO LASCO C2/C3 · OBSERVED 2015-03-15",
        heading: "Two days before the storm, the cloud leaves",
        caption:
          "The date burned into these frames is 15 March. The storm this event is named " +
          "for is the 17th. What separates them is transit time across 150 million " +
          "kilometres, and nothing in this picture tells you the cloud was pointed at us.",
        provenance: HELIOVIEWER,
      },
    ],
  },

  "quebec-1989": {
    clips: [],
    absence: {
      heading: "There is no footage of this one",
      caption:
        "SOHO's archive begins in 1996 and SDO's in 2010. In March 1989 no space-based " +
        "solar observatory was watching, so the record for this storm is ground " +
        "magnetometers and a failed power grid rather than a picture of the Sun.",
      narration: "quebec-1989-no-imagery",
    },
  },
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/**
 * One clip. `preload="none"` plus a poster is the whole performance story: the page
 * costs one small JPEG per clip on load and fetches no video bytes until a visitor
 * presses play.
 */
function clipFigure(clip: MediaClip): string {
  const video = asset(`${clip.stem}.mp4`);
  const poster = asset(`${clip.stem}.jpg`);
  return `
    <figure class="oi-figure oi-${clip.evidence}">
      <figcaption class="oi-head">
        ${evidenceBadge(clip.evidence === "illustration" ? "schematic" : "observed")}<span class="layer-status-note">${escapeHtml(clip.badge)}</span>
        <strong>${escapeHtml(clip.heading)}</strong>
      </figcaption>
      <video class="oi-video" preload="none" poster="${poster}" controls loop muted playsinline
             aria-label="${escapeHtml(clip.heading)}">
        <source src="${video}" type="video/mp4" />
      </video>
      <p class="oi-caption">${escapeHtml(clip.caption)}</p>
      <details class="oi-provenance"><summary>Where this came from</summary><p>${escapeHtml(clip.provenance)}</p></details>
    </figure>
  `;
}

function absenceFigure(absence: NonNullable<EventMedia["absence"]>): string {
  return `
    <figure class="oi-figure oi-absent">
      <figcaption class="oi-head"><strong>${escapeHtml(absence.heading)}</strong></figcaption>
      <p class="oi-caption">${escapeHtml(absence.caption)}</p>
      ${narrationBlock(absence.narration)}
    </figure>
  `;
}

/**
 * How many pieces of INSTRUMENT FOOTAGE this event holds. Generated
 * illustrations are deliberately not counted: `eventCard` uses this to tell a
 * reader what an event has before they open it, and an illustration is not
 * evidence about the event, which is the whole reason the two classes are kept
 * in separate groups below.
 */
export function eventObservedClipCount(eventId: string): number {
  return (EVENT_MEDIA[eventId]?.clips ?? []).filter((clip) => clip.evidence === "observed").length;
}

/** The block for one event, or "" for an event this module holds nothing for. */
export function observedImageryBlock(eventId: string): string {
  const media = EVENT_MEDIA[eventId];
  if (!media) return "";

  const observed = media.clips.filter((c) => c.evidence === "observed");
  const illustrated = media.clips.filter((c) => c.evidence === "illustration");

  const parts: string[] = [];
  if (observed.length) {
    parts.push(`<div class="oi-group">${observed.map(clipFigure).join("")}</div>`);
  }
  if (media.absence) {
    parts.push(`<div class="oi-group">${absenceFigure(media.absence)}</div>`);
  }
  // The hard rule. Generated work never sits in the same group, or the same frame,
  // as instrument footage.
  if (illustrated.length) {
    parts.push(`
      <div class="oi-break" role="separator"><span>Everything below this line is drawn, not recorded</span></div>
      <div class="oi-group">${illustrated.map(clipFigure).join("")}</div>
    `);
  }

  return `<section class="observed-imagery" aria-label="Imagery for this event">${parts.join("")}</section>`;
}
