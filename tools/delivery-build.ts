import { readFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import type { Plugin } from 'vite';
// @ts-expect-error jsdom is an existing development dependency without bundled types.
import { JSDOM } from 'jsdom';

export const studyStyle = `body{max-width:64rem;margin:2rem auto;padding:0 1rem;font:17px/1.6 system-ui,sans-serif;color:#172533;background:#fff}a{color:#14547c}summary{cursor:pointer;font-size:1.15rem;font-weight:600;padding:1rem 0}details{border-bottom:1px solid #aab8c2}svg{max-width:100%;height:auto;background:#0e1823;color:#eaf1f8}figure{margin:1.5rem 0}figcaption,.study-limitation{border-left:3px solid #496b81;padding:.5rem 1rem}table{width:100%;border-collapse:collapse}td,th{padding:.5rem;text-align:left;border:1px solid #bbb}h1,h2,h3{line-height:1.2}.fund-terms,.fund-facts,.fund-where{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:1rem}.fund-equation{padding:1rem;background:#f1f5f7}.fund-pager,.fund-page-back{display:none}section{margin:2rem 0}code{overflow-wrap:anywhere}@media print{details>*{display:block!important}}`;

/** Strip active/network elements before HTML ever reaches a reader. Captions stay in place. */
export function staticStudy(html: string, prefix = ''): { title: string; html: string } {
  const dom = new JSDOM(`<body>${html}</body>`);
  const doc = dom.window.document as Document;
  const title = doc.querySelector('h1')?.textContent ?? 'Lesson';
  doc.querySelectorAll('script,link,nav,.fund-page-back').forEach(node => node.remove());
  doc.querySelectorAll('style').forEach(node => {
    if (/@import|url\(\s*['"]?(?!#)/i.test(node.textContent ?? '')) node.remove();
  });
  doc.querySelectorAll('video,audio,iframe,canvas,img,object,embed').forEach(node => {
    const note = doc.createElement('p');
    note.className = 'study-limitation';
    note.textContent = 'Media or interactive figure omitted in static reading. Its explanation and evidence labels follow; open the full explorer for this view.';
    node.replaceWith(note);
  });
  doc.querySelectorAll('button,input,select').forEach(node => {
    const note = doc.createElement('span');
    note.textContent = ` ${node.textContent?.trim() || 'Interactive control'} (full explorer only). `;
    node.replaceWith(note);
  });
  doc.querySelectorAll('*').forEach(node => {
    for (const attr of Array.from(node.attributes)) {
      if (/^on/i.test(attr.name) || ['src','srcset','poster','autoplay'].includes(attr.name)) node.removeAttribute(attr.name);
      if (attr.name === 'style' && /@import|url\(\s*['"]?(?!#)/i.test(attr.value)) node.removeAttribute(attr.name);
    }
  });
  // A copied navigation affordance must never pretend it works in the saved file.
  doc.querySelectorAll('a').forEach(node => {
    const href = node.getAttribute('href') ?? '';
    if (!/^https:\/\//.test(href)) node.replaceWith(doc.createTextNode(node.textContent ?? ''));
    else { node.setAttribute('target','_blank'); node.setAttribute('rel','noopener noreferrer'); }
  });
  doc.querySelectorAll('svg image,svg use').forEach(node => {
    const href = node.getAttribute('href') ?? node.getAttribute('xlink:href');
    if (href && !href.startsWith('#')) node.remove();
  });
  // Each original page owned its IDs. Collected lessons need distinct SVG
  // marker/clip IDs and accessible-label targets in the one saved document.
  if (prefix) {
    const ids = new Map(Array.from(doc.querySelectorAll('[id]'), node => [node.id, `${prefix}-${node.id}`]));
    doc.querySelectorAll('*').forEach(node => {
      for (const attr of Array.from(node.attributes)) {
        let value = attr.value.replace(/url\(#([^)]+)\)/g, (match, id: string) => ids.has(id) ? `url(#${ids.get(id)})` : match);
        if (attr.name === 'id') value = ids.get(value) ?? value;
        if (['aria-labelledby','aria-describedby','for'].includes(attr.name)) value = value.split(' ').map(id => ids.get(id) ?? id).join(' ');
        if (['href','xlink:href'].includes(attr.name) && value.startsWith('#')) value = `#${ids.get(value.slice(1)) ?? value.slice(1)}`;
        node.setAttribute(attr.name,value);
      }
    });
  }
  const result = { title, html: doc.body.innerHTML };
  dom.window.close();
  return result;
}

export const entrance = `<body class="delivery-page">
<main class="delivery-card" id="delivery-entrance">
  <p class="delivery-kicker">SPACE ENVIRONMENT EXPLORER</p>
  <h1>Welcome aboard.</h1>
  <p>Explore satellites and space weather.</p>
  <button class="delivery-primary" id="delivery-enter">Enter explorer</button>
  <p id="delivery-mode-note" class="delivery-note" hidden></p>
  <details id="delivery-options"><summary>Connection &amp; display options</summary>
    <p>Slow link or older computer? Start with lessons, then load more when you need it.</p>
    <label>Data<select id="delivery-data"><option value="auto">Use my browser preference</option><option value="light">On demand — start with lessons</option><option value="full">Standard — load the explorer</option></select></label>
    <label>Display<select id="delivery-display"><option value="auto">Use my browser preference</option><option value="light">Static reading — no 3D</option><option value="full">Interactive 3D</option></select></label>
    <button id="delivery-test">Quick check (optional)</button>
    <p class="delivery-note">One request, at most 16 KiB of sample data plus network headers; stops after 4 seconds. A CPU sample targets 20 ms. No graphics stress test.</p>
    <p id="delivery-test-result" role="status"></p>
    <a class="delivery-download" href="./study.html" download="space-study.html">Download lessons for offline use</a>
    <p class="delivery-note">15 lessons with static figures. No live globe, media, or orbital histories. Read mode also lets you save a dated weather snapshot.</p>
  </details>
  <p class="delivery-note">Personal educational project. Not a Navy or U.S. Government product. Not for operational use. <a href="./study.html#about">About &amp; disclaimer</a></p>
  <p id="delivery-status" class="delivery-status" role="status"></p>
  <noscript><a href="./study.html">Read the lessons without JavaScript</a></noscript>
</main><script type="module" src="/src/delivery-entry.ts"></script></body>`;

export function constrainedDelivery(enabled: boolean): Plugin {
  let shell = '';
  let study = '';
  const probe = randomBytes(16 * 1024);
  async function makeStudy() {
    const { createServer } = await import('vite');
    const server = await createServer({ configFile: false, publicDir: false,
      optimizeDeps: { noDiscovery: true, include: [], entries: [] },
      server: { middlewareMode: true, watch: null }, appType: 'custom' });
    try {
    const source = await server.ssrLoadModule('/tools/study-source.ts');
      const pages = (source.studyPages() as Array<{id:string;html:string}>).map(page => ({ ...page, ...staticStudy(page.html,page.id) }));
      const figureCss = readFileSync('src/satellite-fundamentals.css','utf8').split('/* SVG type.')[1]?.split('/* ── SEE IT LIVE')[0];
      if (!figureCss) throw Error('Figure typography section changed; review static study styling.');
      const root = readFileSync('src/styles.css','utf8').match(/:root\s*\{[^}]+\}/)?.[0];
      if (!root) throw Error('Figure palette unavailable');
      const palette = new Map([...root.matchAll(/(--[\w-]+):\s*(#[a-f0-9]{3,8})\s*;/gi)].map(match => [match[1],match[2]]));
      // Literal fills preserve the source palette even in browsers without CSS variables.
      const svgCss = figureCss.slice(figureCss.indexOf('*/')+2).replace(/var\((--[\w-]+)\)/g, (_match,key:string) => {
        const value = palette.get(key); if (!value) throw Error(`Missing static figure colour: ${key}`); return value;
      });
      const escape = (s:string) => s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
      study = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Space Environment Explorer — offline lessons</title><style>${studyStyle}${svgCss}*{animation:none!important;transition:none!important}.fund-figure-scroll{overflow-x:auto}.fund-figure svg{min-width:760px}body{font-family:system-ui,sans-serif}</style><body>
<header><p>SPACE ENVIRONMENT EXPLORER</p><h1>Study at your own pace.</h1><p>15 lessons · static reading · edition ${new Date().toISOString().slice(0,10)}</p>
<p class="study-limitation">Static figures preserve their published evidence labels and captions. Media and interactive activities are marked where omitted. This edition contains no live conditions or orbital histories.</p>
<p><a href="https://sean.theinformed.org/space/" target="_blank" rel="noopener noreferrer">Open the online explorer</a></p></header>
${pages.map(page => `<details id="${page.id}"><summary>${escape(page.title)}</summary>${page.html}</details>`).join('\n')}
<footer id="about"><h2>About this project</h2><p>LT Sean Egan, PhD, USN &amp; AG1 Derek Conklin, USN.</p>${readFileSync('index.html','utf8').match(/<section class="dialog-disclaimer"[\s\S]*?<\/section>/)?.[0] ?? ''}</footer></body></html>`;
      if (Buffer.byteLength(study) > 4 * 1024 * 1024) throw Error('Static study document exceeds 4 MiB budget');
    } finally { await server.close(); }
  }
  return {
    name: 'constrained-delivery',
    async buildStart() { if (enabled) await makeStudy(); },
    transformIndexHtml: { order: 'pre', handler(html) {
      if (!enabled) return html;
      shell = html.match(/<body[^>]*>([\s\S]*)<\/body>/i)![1]!.replace(/<script\b[\s\S]*?<\/script>/gi, '');
      return html.replace(/<body[^>]*>[\s\S]*<\/body>/i, entrance);
    } },
    configureServer(server) {
      if (!enabled) return;
      server.middlewares.use(async (req,res,next) => {
        const path = req.url?.split('?')[0];
        if (!['/study.html','/app-shell.html','/assets/delivery-probe.bin'].includes(path ?? '')) return next();
        if (path === '/app-shell.html') {
          const html = readFileSync('index.html','utf8');
          res.setHeader('Content-Type','text/html');
          return res.end(html.match(/<body[^>]*>([\s\S]*)<\/body>/i)![1]!.replace(/<script\b[\s\S]*?<\/script>/gi,''));
        }
        if (path === '/study.html') { res.setHeader('Content-Type','text/html'); return res.end(study); }
        res.setHeader('Content-Type','application/octet-stream'); res.setHeader('Cache-Control','no-store'); return res.end(probe);
      });
    },
    generateBundle() {
      if (!enabled) return;
      this.emitFile({type:'asset',fileName:'app-shell.html',source:shell});
      this.emitFile({type:'asset',fileName:'study.html',source:study});
      this.emitFile({type:'asset',fileName:'study.html.gz',source:gzipSync(study)});
      this.emitFile({type:'asset',fileName:'assets/delivery-probe.bin',source:probe});
    },
  };
}
