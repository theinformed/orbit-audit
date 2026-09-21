// Bundle/DOM checks only: jsdom does not launch a browser or enable resources.
// Usage: node tools/check-delivery-build.mjs ENABLED_DIR DISABLED_DIR
// stdout is a <4 KiB report. No disk/network writes, no service worker, no GPU.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { gzipSync, gunzipSync } from 'node:zlib';
import { JSDOM } from 'jsdom';

const [enabled, disabled] = process.argv.slice(2);
assert(enabled && disabled, 'Supply enabled and disabled build directories');
const read = (dir,path) => readFileSync(`${dir}/${path}`);
const doc = (dir,path) => new JSDOM(read(dir,path).toString()).window.document;
const html = doc(enabled,'index.html');
assert(html.getElementById('delivery-entrance'));
assert(!html.querySelector('details').open);
assert.equal(html.querySelectorAll('.delivery-primary').length,1);
assert(!html.getElementById('scene'));
assert.equal(html.querySelectorAll('script').length,1);
assert.equal(html.querySelectorAll('[rel=modulepreload]').length,0);
const manifest = JSON.parse(read(enabled,'.vite/manifest.json'));
const entry = manifest['index.html'];
assert(!entry.imports?.length,'Entrance must not statically import the application');
assert(entry.dynamicImports.includes('src/main.ts'));
assert(read(enabled,entry.file).length < 20*1024,'Entrance script budget');
assert.equal(read(enabled,'assets/delivery-probe.bin').length,16384);
const study = doc(enabled,'study.html');
assert.equal(study.querySelectorAll('body > details').length,15);
assert.equal(study.querySelectorAll('svg').length,13);
assert.equal(study.querySelectorAll('script,video,audio,img,canvas,iframe,link,object,embed,image,animate,animateMotion,animateTransform,set,[src],[srcset],[poster]').length,0);
const ids = [...study.querySelectorAll('[id]')].map(node=>node.id);
assert.equal(new Set(ids).size,ids.length,'SVG and accessible label IDs must be unique');
assert(study.querySelectorAll('.study-limitation').length>1);
assert(study.body.textContent.includes('Do not use this site for operations.'));
assert(read(enabled,'study.html').length<=4*1024*1024);
assert.deepEqual(gunzipSync(read(enabled,'study.html.gz')),read(enabled,'study.html'));
assert(doc(enabled,'app-shell.html').getElementById('scene'));
assert(!doc(enabled,'app-shell.html').querySelector('script'));
const original=doc(disabled,'index.html');
assert(original.getElementById('welcome-dialog'));
assert(!original.getElementById('delivery-entrance'));
assert(!existsSync(`${disabled}/study.html`),'Flag off must not publish feature artifacts');
function footprint(dir) {
  const entry=JSON.parse(read(dir,'.vite/manifest.json'))['index.html'];
  const files=['index.html',entry.file,...entry.css];
  return files.map(path=>({path,decodedBytes:read(dir,path).length,gzip6Bytes:gzipSync(read(dir,path)).length}));
}
const firstScreen=html.getElementById('delivery-entrance').cloneNode(true);
firstScreen.querySelectorAll('details').forEach(node=>node.replaceWith(node.querySelector('summary').cloneNode(true)));
firstScreen.querySelectorAll('noscript').forEach(node=>node.remove());
const words=node=>node.textContent.trim().split(/\s+/).length;
console.log(JSON.stringify({checkedAt:new Date().toISOString(),checks:'passed; no browser launched',
  enabledEntry:footprint(enabled),disabledEntry:footprint(disabled),
  welcomeWords:{before:words(original.getElementById('welcome-dialog')),after:words(firstScreen)},
  study:{lessons:15,svgFigures:13,decodedBytes:read(enabled,'study.html').length,gzip6Bytes:read(enabled,'study.html.gz').length},
  probeBodyBytes:16384},null,2));
