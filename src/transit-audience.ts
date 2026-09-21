/**
 * Two presentations of one engine.
 *
 * The site owner wanted both a teaching surface for the public and a genuinely
 * useful tool for the Navy Space Cadre and METOC officers the site is written
 * for. Those are different framings, not different answers.
 *
 * ## The rule that makes this safe
 *
 * **The computation is identical.** Same solver, same elevation mask, same
 * visibility geometry, same capability dataset, same citations. Nothing in this
 * file reaches `solveSatelliteVisibility`, `elevationDeg`, or the capability
 * matching, and nothing in it may ever be allowed to. If the two presentations
 * could disagree about when a satellite is visible, the split would be a bug
 * generator rather than a feature — so the only things that vary here are
 * wording, affordances, and one bound whose difference is argued for below.
 *
 * ## Why the disclosure is STRONGER behind the gate
 *
 * The intuition runs the other way and the intuition is wrong. A `.mil` reader
 * is *more* likely to mistake fitted public elements for something authoritative,
 * because the gated build will look like tooling they already use and trust. The
 * public reader is being taught and knows it. So the gated build gets the louder
 * notice, repeated at the point of export, stamped into every row of every file
 * it emits.
 *
 * ## The one number that differs, and why that is legitimate
 *
 * The forward-horizon cap. The physics is identical — SGP4 propagates mean
 * elements fitted near an epoch and its error grows without a bound the elements
 * can report. What differs is who is reading the element-age warning. A public
 * visitor cannot be expected to weigh "these elements are eleven days old"
 * against an answer; a watch officer can, and refusing to show them anything
 * past two weeks would make the tool useless for exactly the planning horizon
 * they work on. So the gated build extends the cap and makes element age
 * unmissable rather than merely present. Both remain bounded; neither pretends
 * a 60-day propagation is worth showing.
 */

export type Audience = "public" | "gated";

export interface AudienceProfile {
  audience: Audience;
  /** Nav label and page heading. */
  navLabel: string;
  title: string;
  /** One sentence under the title. */
  standfirst: string;
  /**
   * Public only: the lesson a visitor meets before the apparatus. Null in the
   * gated build, where burying the tool under a lecture would be patronising to
   * a reader who already knows why orbits determine coverage.
   */
  lesson: LessonBlock | null;
  /** Word for the route editor, which is apparatus in one build and a plan in the other. */
  routeHeading: string;
  /** Hard refusal bound on element age at the end of the transit, days. */
  maximumElementAgeDays: number;
  /** Export affordances. Off on the public site; see docs/transit-planner-wiring.md. */
  exportEnabled: boolean;
  /** Element age gets its own column and a banner rather than a detail line. */
  prominentElementAge: boolean;
  /** Extra paragraph appended to the standing disclosure. */
  additionalDisclosure: string | null;
  /** Public build only: honest description of what is behind the gate. */
  gatedLink: { href: string; label: string; description: string } | null;
}

export interface LessonBlock {
  heading: string;
  paragraphs: string[];
  /** Three short claims the tool below then demonstrates. */
  points: Array<{ title: string; body: string }>;
}

const SHARED_LESSON: LessonBlock = {
  heading: "An orbit decides who can see you, and when",
  paragraphs: [
    "A satellite is not a thing in the sky so much as a path around the Earth. Where that path goes, and how fast, decides which patches of ocean can see it at any instant — and nothing about who wants to use it changes that. This page lets you draw a route across the Earth and watch the answer fall out of the geometry.",
    "Three facts do almost all of the work, and you can watch each of them bite by moving one control below.",
  ],
  points: [
    {
      title: "Height sets how much of the Earth a satellite can see at once",
      body: "From 400 km a satellite's horizon reaches about 2,200 km in every direction — a fifth of the way to the pole, and 3% of the Earth's surface. From geostationary altitude, 35,786 km, it reaches 81 degrees of arc and sees 42% of the planet at once. That is the whole reason a handful of geostationary satellites can carry global traffic while a low-orbit constellation needs thousands.",
    },
    {
      title: "A satellite low on your horizon is not usable, and the mask is where you say so",
      body: "The geometric horizon is zero degrees of elevation, and no terminal works there. Raise the minimum elevation and coverage shrinks fast: a geostationary satellite reaches 81.3° of arc away at 0°, 76.3° at 5°, and 71.4° at 10°. Each degree of mask costs almost exactly a degree of arc — 60 nautical miles of reach in every direction, so about 120 nm off a transit that crosses the footprint, and 600 nm by the time you have raised it to 10°. That is why the mask is the first control on this page and not a hidden default.",
    },
    {
      title: "Latitude decides whether a geostationary satellite is any use at all",
      body: "A geostationary satellite sits over the equator. The further north or south you go, the lower it sits on your horizon, until it disappears under it. That is not a capacity problem or a contract problem; it is arithmetic, and it is why high-latitude coverage needs a different orbit entirely. Put a waypoint in the Arctic and watch which systems survive.",
    },
  ],
};

const PUBLIC_PROFILE: AudienceProfile = {
  audience: "public",
  navLabel: "Orbits & coverage",
  title: "Why an orbit decides who can see you",
  // Cut from 30 words to 15 on 2026-08-19. The clause that went — "the route is
  // the worked example; the geometry is the lesson" — is the lesson fold's whole
  // subject, so it is said once instead of twice.
  standfirst:
    "Draw a route. See which satellites could see a ship on it, and when they could not.",
  lesson: SHARED_LESSON,
  routeHeading: "Draw a route to work through",
  maximumElementAgeDays: 14,
  exportEnabled: false,
  prominentElementAge: true,
  additionalDisclosure: null,
  gatedLink: {
    href: "#transit-planner-gated",
    label: "There is a fuller version of this tool",
    description:
      "The same computation, presented as a planning tool rather than a lesson, with data export and a longer forward horizon. It is behind a sign-in intended for U.S. Navy Space Cadre and METOC officers and others working in the field — not because the physics is sensitive, but because the export turns an answer into a document, and a document should go to a reader equipped to judge how far to trust it. Everything it computes, this page computes too.",
  },
};

const GATED_PROFILE: AudienceProfile = {
  audience: "gated",
  navLabel: "Transit planner",
  title: "Transit SATCOM visibility planner",
  standfirst:
    "Visibility windows, coverage gaps and constellation continuity over a routed transit, from public orbital elements.",
  lesson: null,
  routeHeading: "Route",
  // Extended over the public build's 14 days, deliberately: see the module note.
  maximumElementAgeDays: 30,
  exportEnabled: true,
  prominentElementAge: true,
  additionalDisclosure:
    "This build looks like tooling you already use, and it is not that. Every position here comes from publicly distributed mean elements propagated with SGP4 — the same public general-perturbations data anyone can download, carrying no covariance, blind to every manoeuvre since its epoch, and fitted rather than measured. It is not an operational ephemeris, it has not been through any operational validation, and a satellite repositioned since its last published element set will be in the wrong place here with no indication that it is. Check the element age on every row before you rely on a window. Nothing here is a substitute for authoritative SATCOM planning products or for the SATCOM System Expert.",
  gatedLink: null,
};

export function audienceProfile(audience: Audience): AudienceProfile {
  return audience === "gated" ? GATED_PROFILE : PUBLIC_PROFILE;
}

/**
 * The one line that must appear on every exported row and every file header.
 *
 * Exported here rather than written at the call site so a future format cannot
 * be added without it: the CSV writer, any print view, and the file header all
 * read this constant. A document that leaves the browser without this line is
 * the failure mode the public build avoids by having no export at all.
 */
export const EXPORT_PROVENANCE_LINE =
  "Computed from publicly distributed mean orbital elements propagated with SGP4. "
  + "Fitted prediction, not an operational ephemeris. Line-of-sight geometry only: "
  + "says nothing about beam pointing, capacity assignment, terminal certification, "
  + "or whether a link would close. Educational use.";
