/** Publish-time CPU SVG renderer. Offline stdin -> stdout; no browser/GPU/network. */
import { json2satrec, propagate, gstime, eciToGeodetic } from 'satellite.js';
import { pathToFileURL } from 'node:url';
const D = Math.PI / 180;
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const xy = ([lon,lat]) => [40+(lon+180)*2,80+(90-lat)*2];
function line(points, colour, width=1) {
  let d='', previous=null;
  for (const point of points) {
    const p=xy(point);
    d+=`${previous && Math.abs(point[0]-previous[0])<180 ? 'L':'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`;
    previous=point;
  }
  return `<path d="${d}" fill="none" stroke="${colour}" stroke-width="${width}"/>`;
}
function map(land) {
  let s='<rect x="40" y="80" width="720" height="360" fill="#e8f3fa" stroke="#637c8b"/>';
  for(let lat=-60;lat<=60;lat+=30) s+=line([[-180,lat],[0,lat],[179.9,lat]],'#c3d4dd');
  for(let lon=-180;lon<=180;lon+=60) s+=line([[lon,-90],[lon,90]],'#c3d4dd');
  for(const feature of land.features ?? []) {
    const polygons=feature.geometry.type==='Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
    for(const polygon of polygons) for(const ring of polygon) s+=line(ring,'#607b6b',.7);
  }
  return s;
}
function label(x,y,text,size=13) { return `<text x="${x}" y="${y}" font-size="${size}" fill="#172533">${esc(text)}</text>`; }
function frame(title,at,body,notes) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 ${490+notes.length*20}" role="img"><title>${esc(title)} — ${esc(at)}</title><rect width="100%" height="100%" fill="white"/><g font-family="sans-serif">${label(20,26,title,20)}${label(20,50,`Snapshot: ${at} UTC — not live`)}${body}${notes.map((note,i)=>label(20,475+i*20,note)).join('')}</g></svg>`;
}
function subpoint(satellite,date) {
  try {
    const pv=propagate(json2satrec(satellite.omm),date);
    if(!pv || !pv.position || typeof pv.position==='boolean') return null;
    const g=eciToGeodetic(pv.position,gstime(date));
    if (![g.longitude,g.latitude,g.height].every(Number.isFinite) || g.height < 0) return null;
    return { satellite,lon:g.longitude/D,lat:g.latitude/D,height:g.height };
  } catch { return null; }
}
function greatCircle(a,b) {
  const vector=([lon,lat])=>[Math.cos(lat*D)*Math.cos(lon*D),Math.cos(lat*D)*Math.sin(lon*D),Math.sin(lat*D)];
  const u=vector(a),v=vector(b),angle=Math.acos(Math.max(-1,Math.min(1,u.reduce((s,x,i)=>s+x*v[i],0))));
  return Array.from({length:121},(_,i)=>{
    const t=i/120, p=u.map((x,j)=>(Math.sin((1-t)*angle)*x+Math.sin(t*angle)*v[j])/Math.sin(angle));
    return [Math.atan2(p[1],p[0])/D,Math.atan2(p[2],Math.hypot(p[0],p[1]))/D];
  });
}
function footprint(p) {
  // Same spherical elevation-angle formula used for nonzero elevation in orbit.ts.
  const e=10*D, r=Math.acos(6371/(6371+p.height)*Math.cos(e))-e;
  const lat=p.lat*D,lon=p.lon*D;
  return Array.from({length:181},(_,i)=>{
    const b=i/180*2*Math.PI,phi=Math.asin(Math.sin(lat)*Math.cos(r)+Math.cos(lat)*Math.sin(r)*Math.cos(b));
    const lam=lon+Math.atan2(Math.sin(b)*Math.sin(r)*Math.cos(lat),Math.cos(r)-Math.sin(lat)*Math.sin(phi));
    return [((lam/D+540)%360)-180,phi/D];
  });
}
export function renderFigures({catalog,land,generatedAt}) {
  const date=new Date(generatedAt);
  if (!Number.isFinite(date.getTime())) throw Error('Snapshot timestamp required');
  const satellites=catalog.satellites;
  const points=satellites.map(s=>subpoint(s,date)).filter(Boolean);
  // Density cells preserve every valid subpoint count, avoiding thousands of SVG nodes.
  const cells=new Map();
  for(const p of points) {
    const key=`${Math.floor((p.lon+180)/2)},${Math.min(89,Math.floor((p.lat+90)/2))}`;
    cells.set(key,(cells.get(key) ?? 0)+1);
  }
  let density=''; const max=Math.max(1,...cells.values());
  for(const [key,count] of cells) {
    const [x,y]=key.split(',').map(Number);
    density+=`<rect x="${40+x*4}" y="${80+356-y*4}" width="4" height="4" fill="#075c9c" opacity="${(.2+.8*Math.log1p(count)/Math.log1p(max)).toFixed(2)}"><title>${count} satellite subpoints in this 2° cell</title></rect>`;
  }
  const common=map(land);
  const epochs=satellites.map(s=>s.omm?.EPOCH).filter(v=>typeof v==='string').sort();
  const epochNote=`Element epochs: ${epochs[0] ?? 'unavailable'} to ${epochs.at(-1) ?? 'unavailable'}`;
  const globe=frame('Globe alternative · satellite subpoint density',generatedAt,common+density,[
    `SGP4 model: ${points.length} of ${satellites.length} catalog objects propagated; ${satellites.length-points.length} unavailable and omitted.`,
    `2° geographic cells; darker = more objects (maximum ${max}/cell). Counts retained, positions grouped.`,
    'Flat map of positions beneath satellites; not orbital altitude, live observations or weather layers.',
    'Sources: Space-Track mean elements; Natural Earth 110m coastlines.',
    epochNote,
  ]);
  const waypoints=[[-75.7,36.95],[-9.6,36.6],[-6.7,36.4]];
  let route=line([...greatCircle(waypoints[0],waypoints[1]),...greatCircle(waypoints[1],waypoints[2])],'#a64300',2.5);
  // Deterministic, disclosed worked subset; never imply all potential links were tested.
  const chosen=points.filter(p=>p.satellite.orbit==='GEO' && p.satellite.mission==='communications' && p.lon>-80 && p.lon<10).sort((a,b)=>a.satellite.id-b.satellite.id).slice(0,3);
  for(const p of chosen) {
    route+=line(footprint(p),'#0968ac',1.2);
    const [x,y]=xy([p.lon,p.lat]); route+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="#0968ac"/>`;
    route+=label(x+4,y-5,String(p.satellite.id),11);
  }
  route+=label(205,205,'Norfolk',12)+label(749,213,'Rota',12);
  const transit=frame('Transit globe alternative · Norfolk → Rota worked example',generatedAt,common+route,[
    'Orange: great-circle legs through Chesapeake, Cape St Vincent and Rota approaches.',
    `Blue: ${chosen.length} selected GEO communications subpoints and spherical 10°-elevation footprints.`,
    chosen.length ? `NORAD ${chosen.map(p=>p.satellite.id).join(', ')}; first three IDs in the −80° to 10° longitude band.` : 'No eligible satellites available; footprints are missing, not demonstration data.',
    'Geometric model only; not service access, guaranteed contact, or a custom route prediction.',
    'Flat projection distorts area; altitude, motion, weather and interactive selections are omitted.',
    'Sources: Space-Track mean elements; Natural Earth 110m coastlines.',
    epochNote,
  ]);
  return {globe,transit};
}
if (process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  let input=''; for await(const chunk of process.stdin) input+=chunk;
  process.stdout.write(JSON.stringify(renderFigures(JSON.parse(input))));
}
