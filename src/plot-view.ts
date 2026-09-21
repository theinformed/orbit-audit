/** Small JSON display derivatives; imported without any renderer or catalogue. */
import { boundedBody } from './delivery-policy';
import type { OrbitHistoryObject, OrbitSample } from './orbit-history';

export const PLOT_LIMIT = 4 * 1024 * 1024;
export function artifactPath(path: string): string {
  if (!/^artifacts\/[a-z0-9-]+\.(?:json|svg)$/.test(path)) throw Error('Invalid published artifact path');
  return `data/${path}`;
}
export async function smallJson(path: string): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(new URL(path, document.baseURI), { signal: controller.signal, redirect: 'error' });
    return JSON.parse(new TextDecoder().decode(await boundedBody(response, PLOT_LIMIT)));
  } finally { clearTimeout(timer); }
}
export function decodePlot(value: unknown): OrbitHistoryObject {
  const v = value as Record<string, unknown>;
  const display = v?.display as OrbitHistoryObject['display'];
  if (v?.schema !== 1 || !Number.isInteger(v.norad) || !Array.isArray(v.points) || !Array.isArray(v.events)
    || !display || display.method !== 'vertical-error-extrema-v1'
    || display.displayPoints !== v.points.length || !Number.isInteger(display.originalPoints)
    || display.originalPoints < v.points.length || !Number.isFinite(display.maxErrorPixels)
    || display.panelHeight !== 96 || typeof display.evidenceNote !== 'string') throw Error('Invalid plot view');
  artifactPath(display.fullPath);
  const samples: OrbitSample[] = v.points.map((p: unknown) => {
    if (!Array.isArray(p) || p.length !== 10 || !p.slice(0,6).every(Number.isFinite)
      || !(p[6] === null || Number.isFinite(p[6])) || !['full','daily'].includes(p[7])
      || !Number.isFinite(p[8]) || typeof p[9] !== 'boolean') throw Error('Invalid plot sample');
    return { t:p[0],perigeeKm:p[1],apogeeKm:p[2],semiMajorAxisKm:p[3],inclinationDeg:p[4],
      eccentricity:p[5],bstar:p[6],tier:p[7],residualMetres:p[8],joinPrevious:p[9] };
  });
  if (samples.some((s,i) => i > 0 && s.t < samples[i-1]!.t)) throw Error('Unsorted plot view');
  return { norad:v.norad as number, samples, events:v.events as OrbitHistoryObject['events'], display };
}
export async function fetchPlotObject(path: string) { return decodePlot(await smallJson(path)); }
export function plotNotice(record: OrbitHistoryObject): string {
  const d = record.display!;
  return `Decimated series: ${d.displayPoints.toLocaleString('en-US')} of ${d.originalPoints.toLocaleString('en-US')} points. Original samples retained within ${d.maxErrorPixels} pixel at ${d.panelHeight}-pixel panel height and normal zoom; use full resolution for closer inspection. ${d.evidenceNote} Repeat-cluster details require full resolution.`;
}

/** Static SVG curves, including isolated observations and explicit missing runs. */
export function plotFigure(record: OrbitHistoryObject): HTMLElement {
  const section = document.createElement('section');
  const title = document.createElement('h2'); title.textContent = `Orbit history · NORAD ${record.norad}`;
  const note = document.createElement('p'); note.textContent = plotNotice(record);
  const evidence = document.createElement('p');
  evidence.textContent = 'Fitted orbital elements, not measured positions or confirmed manoeuvres. Gaps are left blank. Event evidence is available in the full-resolution archive.';
  section.append(title,note,evidence);
  const full = document.createElement('a'); full.href = artifactPath(record.display!.fullPath);
  full.textContent = 'Full-resolution JSON and evidence (large download)'; full.setAttribute('download',''); section.append(full);
  const samples = record.samples;
  if (!samples.length) { const p=document.createElement('p'); p.textContent='No samples published.'; section.append(p); return section; }
  const t0=samples[0]!.t, t1=samples[samples.length-1]!.t;
  const dates=document.createElement('p'); dates.textContent=`Element epochs: ${new Date(t0).toISOString()} to ${new Date(t1).toISOString()}.`; section.append(dates);
  const channels: Array<[string,Array<[(s:OrbitSample)=>number,string]>]> = [
    ['Perigee (blue) and apogee (orange) · km', [[s=>s.perigeeKm,'#0968ac'],[s=>s.apogeeKm,'#a64300']]],
    ['Semi-major axis, full-source trend removed · m', [[s=>s.residualMetres!,'#0968ac']]],
    ['Inclination · degrees', [[s=>s.inclinationDeg,'#0968ac']]],
    ['B* drag term · log₁₀ (positive values only)', [[s=>s.bstar !== null && s.bstar > 0 ? Math.log10(s.bstar) : NaN,'#0968ac']]],
  ];
  for (const [label,series] of channels) {
    const fig=document.createElement('figure'); const caption=document.createElement('figcaption'); caption.textContent=label; fig.append(caption);
    const all=series.flatMap(([value])=>samples.map(value)).filter(Number.isFinite);
    if (!all.length) { fig.append(document.createTextNode('Unavailable — no valid values.')); section.append(fig); continue; }
    let lo=Math.min(...all), hi=Math.max(...all); if (hi===lo) { lo-=1; hi+=1; }
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 720 136'); svg.setAttribute('role','img'); svg.setAttribute('aria-label',`${label}; ${lo} to ${hi}. Missing data left blank.`);
    svg.style.cssText='display:block;width:100%;max-width:720px;background:white';
    const x=(t:number)=>50+(t-t0)/(t1-t0 || 1)*660;
    const y=(v:number)=>10+(hi-v)/(hi-lo)*96;
    for (const [value,colour] of series) {
      let d=''; let prior=false;
      for (const s of samples) {
        const v=value(s); if (!Number.isFinite(v)) { prior=false; continue; }
        const px=x(s.t).toFixed(2), py=y(v).toFixed(2);
        d+=`${prior && s.joinPrevious ? 'L':'M'}${px},${py}`;
        // A tiny segment makes an isolated observation visible in the same path.
        d+=`l0.01,0`; prior=true;
      }
      const path=document.createElementNS(svg.namespaceURI,'path'); path.setAttribute('d',d); path.setAttribute('fill','none'); path.setAttribute('stroke',colour); path.setAttribute('stroke-width','1'); path.setAttribute('stroke-linecap','round'); svg.append(path);
    }
    for (const [v,py] of [[hi,12],[lo,108]]) {
      const tick=document.createElementNS(svg.namespaceURI,'text'); tick.setAttribute('x','0'); tick.setAttribute('y',String(py)); tick.setAttribute('font-size','10'); tick.setAttribute('fill','#172533'); tick.textContent=v!.toPrecision(5); svg.append(tick);
    }
    fig.append(svg); section.append(fig);
  }
  return section;
}
