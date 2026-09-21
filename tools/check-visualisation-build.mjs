/** Offline manifest dependency check; no browser or resource loading. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root=process.argv[2];assert(root,'Supply constrained build directory');
const manifest=JSON.parse(readFileSync(`${root}/.vite/manifest.json`,'utf8'));
const visited=new Set();
function visit(key) {
  if(visited.has(key))return;
  assert(!['src/main.ts','src/energy-chain-view.ts'].includes(key),'Static reader imported the application');
  visited.add(key);
  for(const dependency of manifest[key]?.imports ?? [])visit(dependency);
}
assert(manifest['index.html'].dynamicImports.includes('src/static-data-views.ts'));
assert(!manifest['index.html'].imports?.length,'Entrance acquired an eager dependency');
visit('src/static-data-views.ts');
const files=[...visited].map(key=>manifest[key].file);
let bytes=0;
for(const file of files) {
  const body=readFileSync(`${root}/${file}`,'utf8');bytes+=Buffer.byteLength(body);
  assert(!body.includes('WebGLRenderer'),'Static reader acquired WebGL');
}
assert(bytes<64*1024,'Constrained visualisation JS exceeds 64 KiB budget');
console.log(JSON.stringify({result:'passed',files,decodedJavaScriptBytes:bytes,webgl:false,browserLaunched:false},null,2));
