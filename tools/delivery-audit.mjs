// Offline inventory. Reads current references; never launches a browser or fetches upstream.
// Usage: node tools/delivery-audit.mjs /tmp/build [--out docs/delivery-baseline]
// Without --out this is a dry run. Reports only, capped at 10 MiB / 3 files;
// each explicit output prefix replaces its own reports. Builds belong in /tmp.
import { readdirSync, readFileSync, statSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { gzipSync, brotliCompressSync, constants } from 'node:zlib';

const build = process.argv[2];
if (!build) throw Error('Supply a built directory (publicDir:false is sufficient).');
const manifest = JSON.parse(readFileSync('public/data/manifest.json', 'utf8'));
const current = new Map();
for (const [key, record] of Object.entries(manifest)) {
  if (typeof record !== 'object' || !record) continue;
  for (const item of record.path ? [record] : record.shards ?? []) current.set(`data/${item.path}`, key);
}
const rows = [];
function walk(root, prefix = '') {
  for (const entry of readdirSync(join(root, prefix), { withFileTypes: true })) {
    const path = join(prefix, entry.name);
    if (entry.isDirectory()) { walk(root, path); continue; }
    const full = join(root, path);
    const bytes = statSync(full).size;
    let kind = current.get(path) ?? (path.startsWith('data/artifacts/') ? 'unreferenced-artifact' : extname(path).slice(1));
    let phase = ['catalog', 'spaceWeather', 'events', 'land'].includes(kind) ? 'before-globe-interaction'
      : current.has(path) ? 'on-demand' : 'available-not-proven-requested';
    if (path === 'data/manifest.json') phase = 'before-globe-interaction';
    if (root === build && /\.(js|css)$/.test(path)) phase = path.includes('worker') ? 'worker-on-construction' : 'entry-or-import';
    if (path === 'index.html') phase = 'first-paint-html';
    let gzipBytes = existsSync(`${full}.gz`) ? statSync(`${full}.gz`).size : null;
    if (gzipBytes === null && bytes < 4e6 && /\.(html|js|css)$/.test(path)) gzipBytes = gzipSync(readFileSync(full)).length;
    rows.push({ root, path, kind, phase, bytes, gzipBytes });
  }
}
walk(build); walk('public');
const groups = {};
for (const row of rows) {
  if (row.path.endsWith('.gz') || row.path.endsWith('.br')) continue;
  const group = groups[row.kind] ??= { requestsIfAllUsed: 0, bytes: 0, gzipBytes: 0, unknownCompression: 0 };
  group.requestsIfAllUsed++; group.bytes += row.bytes;
  if (row.gzipBytes === null) group.unknownCompression++; else group.gzipBytes += row.gzipBytes;
}
const samples = {};
for (const key of ['catalog', 'orbitEvents', 'spaceWeather']) {
  const buffer = readFileSync(`public/data/${manifest[key].path}`);
  samples[key] = { decoded: buffer.length, gzipExisting: statSync(`public/data/${manifest[key].path}.gz`).size,
    brotliQuality5: brotliCompressSync(buffer, { params: { [constants.BROTLI_PARAM_QUALITY]: 5 } }).length };
}
const summary = { measuredAt: new Date().toISOString(), release: manifest.release,
  method: 'Filesystem bytes + source dependency audit, not a browser timing or HAR. gzip for build text is locally computed, not a live wire measurement.',
  groups, samples, topBytes: rows.filter(r => current.has(r.path)).sort((a,b) => b.bytes-a.bytes).slice(0,15),
  topRequestCounts: Object.entries(groups).sort((a,b) => b[1].requestsIfAllUsed-a[1].requestsIfAllUsed).slice(0,15) };
const csv = 'root,path,kind,phase,bytes,gzipBytes\n' + rows.map(r => Object.values(r).join(',')).join('\n') + '\n';
const outIndex = process.argv.indexOf('--out');
if (outIndex !== -1) {
  const out = process.argv[outIndex+1];
  const json = JSON.stringify(summary, null, 2)+'\n';
  if (Buffer.byteLength(csv)+Buffer.byteLength(json)>10*1024*1024) throw Error('Report budget exceeded');
  mkdirSync(dirname(out), { recursive:true });
  writeFileSync(`${out}.csv`, csv); writeFileSync(`${out}.json`, json);
}
console.log(JSON.stringify({ release: summary.release, samples, currentGroups: Object.fromEntries(Object.entries(groups).filter(([k]) => manifest[k])) },null,2));
