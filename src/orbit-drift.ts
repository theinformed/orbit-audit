/** Independent long-arc lane. No certainty may be borrowed from step controls. */
export const DRIFT_COLOUR = "var(--oh-drift, #57c7b3)";

export interface DriftObject {
  norad: number;
  objectType: string;
  gap: string | null;
  inGate: boolean | null;
  regime: string | null;
  raising: boolean;
  flag: boolean;
  slopeMetresPerDay: number | null;
  spanDays: number | null;
}

export interface OrbitDriftBundle {
  schema: 1;
  version: 4;
  generatedAt: string;
  method: { restrictedPopulation: boolean; windows: [[number, number], [number, number]] };
  controls: {
    acceptance?: string;
    restrictedPopulation: boolean;
    sufficientToLabel: boolean;
    passive: { objects: number; flags: number; upper95: number | null };
    payload: { objects: number; flags: number };
    separation: number | null;
    objectsWithGap: number;
  };
  labelPolicy: { propulsionLabelPermitted: boolean; blockingReason: string | null };
  objects: DriftObject[];
}

export function driftGatePassed(bundle: OrbitDriftBundle): boolean {
  const c = bundle.controls;
  return bundle.version === 4 && bundle.method.restrictedPopulation === false
    && c.restrictedPopulation === false && c.sufficientToLabel === true
    && bundle.labelPolicy.propulsionLabelPermitted === true
    && c.passive.objects > 0 && c.payload.objects > 0
    && c.passive.upper95 !== null && Number.isFinite(c.passive.upper95)
    && c.passive.upper95 > 0 && c.passive.upper95 < .001
    && c.separation !== null && Number.isFinite(c.separation) && c.separation >= 10;
}

const dateOfDay = (day: number) => new Date(day * 86400000).toISOString().slice(0, 10);
export function driftControlText(bundle: OrbitDriftBundle): string {
  const c = bundle.controls;
  const window = bundle.method.windows[1];
  const upper = c.passive.upper95 === null ? "unmeasured" : `${(c.passive.upper95 * 1000).toFixed(3)} per 1,000`;
  const separation = c.separation === null ? "unmeasured" : `${c.separation.toFixed(2)}×`;
  return `Test window ${dateOfDay(window[0])} to ${dateOfDay(window[1])} (end exclusive). `
    + `Passive detections ${c.passive.flags}/${c.passive.objects}; exact one-sided 95% upper bound ${upper}. `
    + `Payload detections ${c.payload.flags}/${c.payload.objects}; payload rate / passive upper bound ${separation}. `
    + `${c.objectsWithGap} objects have test coverage gaps. `
    + (driftGatePassed(bundle) ? "This window's label gate passes. " : `Flags suppressed: ${bundle.labelPolicy.blockingReason || "control gate closed"}. `)
    + "Shared catalogue errors can weaken the binomial bound; individual propulsion is not independently verified.";
}

/** Shared claims: the roster and object card must earn exactly the same wording. */
export function driftObjectText(bundle: OrbitDriftBundle, object: DriftObject): string[] {
  const paragraphs: string[] = [];
  const add = (text: string) => paragraphs.push(text);
  const fit = object.spanDays !== null && Number.isFinite(object.spanDays) && object.spanDays > 0
    && object.slopeMetresPerDay !== null && Number.isFinite(object.slopeMetresPerDay);
  if (object.gap || !fit) {
    add(`Coverage gap: ${object.gap || "test fit unavailable"}. No drift inference is possible for this window.`);
  } else {
    const slope = object.slopeMetresPerDay!;
    const measure = `over ${object.spanDays!.toFixed(1)} days, ${slope >= 0 ? "+" : ""}${slope.toFixed(2)} m/day`;
    if (object.flag && object.raising && object.inGate === true && object.objectType === "PAYLOAD"
        && slope > 0 && driftGatePassed(bundle)) {
      add(`Sustained orbit-raising ${measure}. In this regime, only propulsion produces a sustained climb.`);
      add("Warrant: every raw test-window fit has perigee below 800 km and eccentricity below 0.05; drag removes orbital energy. This window's control supports propulsion by elimination. The cause remains an inference from catalogue fits, not an operator-confirmed burn.");
    } else if (object.raising && object.inGate === false) {
      const labels: Record<string, string> = {
        "SRP-regime rise": "solar-radiation-pressure regime rise",
        "GEO libration": "GEO libration",
        "HEO lunisolar": "HEO lunisolar",
      };
      add(`${labels[object.regime ?? ""] ?? object.regime ?? "Above-gate rise"} ${measure}. This is an ambiguity label, not a demonstrated cause or a propulsion claim.`);
    } else if (object.raising) {
      add(`Resolved positive slope ${measure}; no propulsion claim. `
        + (!driftGatePassed(bundle) ? "This window's control gate is closed." : "This record lacks a permitted payload flag."));
    } else {
      add(`Fitted semi-major-axis slope ${measure}. No resolved sustained raising; lowering is drag-ambiguous. Station-keeping and short campaigns can escape this test.`);
    }
  }
  return paragraphs;
}

export function renderDriftCard(bundle: OrbitDriftBundle, object: DriftObject): HTMLElement {
  const card = document.createElement("section");
  card.className = "orbit-history__status orbit-history__drift";
  card.style.borderLeftColor = DRIFT_COLOUR;
  const title = document.createElement("h3");
  title.textContent = "Long-arc drift";
  card.append(title);
  const add = (text: string) => {
    const p = document.createElement("p");
    p.textContent = text;
    card.append(p);
  };
  driftObjectText(bundle, object).forEach(add);
  add(driftControlText(bundle));
  add(`Drift artifact generated ${bundle.generatedAt}. This is a long-window fit, not a campaign start/end measurement or a Δv estimate.`);
  return card;
}

let cachedPath: string | undefined;
let cachedLoad: Promise<OrbitDriftBundle> | undefined;
/** One current artifact cached by its manifest path; failures remain retryable. */
export function loadOrbitDrift(path: string): Promise<OrbitDriftBundle> {
  if (cachedPath === path && cachedLoad) return cachedLoad;
  cachedPath = path;
  const pending = fetch(new URL(path, new URL("data/manifest.json", document.baseURI)))
    .then(async response => {
      if (!response.ok) throw new Error(`Drift artifact HTTP ${response.status}`);
      const b = await response.json() as OrbitDriftBundle;
      if (b.schema !== 1 || b.version !== 4 || !Array.isArray(b.objects)
          || !b.controls?.passive || !b.controls?.payload || !b.labelPolicy
          || !Array.isArray(b.method?.windows) || b.method.windows.length !== 2
          || b.method.windows.some(w => w.length !== 2 || !w.every(Number.isFinite))) {
        throw new Error("Unsupported drift artifact");
      }
      return b;
    }).catch(error => {
      if (cachedLoad === pending) cachedLoad = undefined;
      throw error;
    });
  cachedLoad = pending;
  return pending;
}

/** The learn chapter consumes the same artifact and gate as the object cards. */
export async function mountDriftControls(host: HTMLElement, path?: string): Promise<void> {
  const target = host.querySelector<HTMLElement>("[data-orbit-drift-controls]");
  if (!target) return;
  if (!path) {
    target.textContent = "No nightly drift control has been published in this release. Propulsion labels are unavailable.";
    return;
  }
  try {
    const bundle = await loadOrbitDrift(path);
    target.textContent = driftControlText(bundle);
  } catch {
    target.textContent = "The published drift control could not be loaded. Its label gate is unavailable; no propulsion claim can be made.";
  }
}
