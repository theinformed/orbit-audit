import './delivery.css';
import {
  boundedBody, deliveryMode, DOCUMENT_LIMIT, parsePreferences, PREFERENCE_KEY,
  runConnectionProbe, runHardwareSample, type DeliveryHints, type DeliveryPreferences,
} from './delivery-policy';

interface BrowserConnection { saveData?: boolean; effectiveType?: string; downlink?: number }
type HintedNavigator = Navigator & { connection?: BrowserConnection; deviceMemory?: number };

function browserHints(): DeliveryHints {
  const matches = (query: string) => typeof matchMedia === 'function' && matchMedia(query).matches;
  return { saveData: (navigator as HintedNavigator).connection?.saveData,
    reducedData: matches('(prefers-reduced-data: reduce)'), reducedMotion: matches('(prefers-reduced-motion: reduce)') };
}

function readPreference(): string | null {
  try { return localStorage.getItem(PREFERENCE_KEY); } catch { return null; }
}
function remember(p: DeliveryPreferences) {
  try { localStorage.setItem(PREFERENCE_KEY, JSON.stringify(p)); } catch { /* Current page still works. */ }
}

async function fetchText(path: string): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(new URL(path, document.baseURI), { signal: controller.signal, redirect: 'error' });
    return new TextDecoder().decode(await boundedBody(response, DOCUMENT_LIMIT));
  } finally { clearTimeout(timeout); }
}

function settingsButton(): HTMLButtonElement {
  const button = document.createElement('button');
  button.className = 'delivery-toolbar';
  button.textContent = 'Connection & display options';
  button.addEventListener('click', () => {
    const url = new URL(location.href);
    url.searchParams.set('deliveryOptions', '1');
    location.assign(url.href); // Unloads the renderer and workers before switching modes.
  });
  return button;
}

export async function startFullExplorer() {
  const html = await fetchText('app-shell.html');
  const shell = document.createElement('template');
  shell.innerHTML = html;
  if (!shell.content.querySelector('#scene')) throw Error('Explorer shell unavailable. Try static reading.');
  document.body.classList.remove('delivery-page');
  document.body.replaceChildren(shell.content);
  document.documentElement.dataset.deliveryEntered = 'true';
  document.body.append(settingsButton());
  try {
    await import('./main');
    await import('./energy-chain-view');
  } catch {
    const message = document.createElement('main');
    message.className = 'delivery-card';
    message.innerHTML = '<h1>The interactive view could not load.</h1><p>A required script is unavailable or unsupported in this browser.</p><p><a href="./study.html">Read the static lessons</a>, or use Connection &amp; display options to try again.</p>';
    document.body.classList.add('delivery-page');
    document.body.replaceChildren(message,settingsButton());
    return;
  }
  const feedback = document.createElement('script');
  feedback.src = new URL('feedback-widget.js', document.baseURI).href;
  document.body.append(feedback);
}

function textNode(tag: string, text: string): HTMLElement {
  const node = document.createElement(tag); node.textContent = text; return node;
}

/** Render only explicit, timestamped source quantities. Missing is never zero. */
export function snapshotTable(weather: Record<string, unknown>, release: string): HTMLElement {
  const section = document.createElement('section');
  section.append(textNode('h2', 'Saved weather readings'), textNode('p',
    `Release ${release}. Retrieved ${new Date().toISOString()}. These are published readings, not a live display; check each observation time. No automatic refresh.`));
  const table = document.createElement('table');
  const heading = document.createElement('tr');
  ['Quantity', 'Value', 'Observed (source timestamp)'].forEach(label => heading.append(textNode('th', label)));
  table.append(heading);
  for (const [group, key, title, unit] of [
    ['solarWind', 'speedKps', 'Solar wind speed', 'km/s'],
    ['solarWind', 'densityCm3', 'Solar wind density', 'cm⁻³'],
    ['imf', 'bzGsmNt', 'IMF Bz (GSM)', 'nT'],
    ['geomagnetic', 'kp', 'Planetary Kp', ''],
    ['xray', 'fluxWm2', 'GOES X-ray flux', 'W/m²'],
  ]) {
    const record = weather[group!] as Record<string, unknown> | undefined;
    const value = record?.[key!];
    const at = record?.observedAt;
    const row = document.createElement('tr');
    row.append(textNode('th', title!), textNode('td', typeof value === 'number' && Number.isFinite(value) ? `${value} ${unit}` : 'Unavailable'),
      textNode('td', typeof at === 'string' ? at : 'Unavailable'));
    table.append(row);
  }
  section.append(table);
  const sources = Array.isArray(weather.sources) ? weather.sources as Array<Record<string,unknown>> : [];
  for (const source of sources) {
    if (typeof source.product !== 'string') continue;
    section.append(textNode('p', `Source: ${source.product} · ${String(source.status ?? 'status unavailable')} · ${String(source.observedAt ?? 'time unavailable')}`));
  }
  return section;
}

export async function startStudy() {
  const study = await fetchText('study.html');
  if (!study.includes('study-limitation') || !study.includes('<details')) throw Error('Study document unavailable. Please try again.');
  document.body.classList.add('delivery-page');
  const main = document.createElement('main');
  main.className = 'delivery-study';
  main.innerHTML = `<h1>Read at your own pace.</h1>
    <p>Static reading: no 3D, animation, or automatic data downloads. Missing media and interactive figures are labelled in each lesson.</p>
    <div class="delivery-actions"><button id="delivery-full">Open interactive explorer</button><button id="delivery-save">Save offline copy</button><button id="delivery-weather">Load weather snapshot</button></div>
    <p class="delivery-note">Save the lessons now and read them later with no connection. Loading weather adds two requests, each limited to 4 MiB of decoded data; normal gzip transfers are smaller. Small orbital plots and dated globe/transit figures can be loaded below and included in the saved copy. Live layers are not included.</p>
    <p id="delivery-study-status" role="status"></p><div id="delivery-weather-readings"></div>
    <div id="delivery-visualisations"></div>
    <iframe title="Satellite and space-weather lessons — static reading" sandbox="allow-popups allow-popups-to-escape-sandbox"></iframe>`;
  main.querySelector('iframe')!.srcdoc = study;
  document.body.replaceChildren(main, settingsButton());
  const { mountStaticDataViews } = await import('./static-data-views');
  mountStaticDataViews(main.querySelector<HTMLElement>('#delivery-visualisations')!);
  const status = main.querySelector<HTMLElement>('#delivery-study-status')!;
  let snapshot: HTMLElement | null = null;
  main.querySelector('#delivery-full')!.addEventListener('click', () => {
    remember({ data:'full', display:'full', entered:true });
    void startFullExplorer().catch(error => { status.textContent = String(error); });
  });
  main.querySelector<HTMLButtonElement>('#delivery-weather')!.addEventListener('click', async event => {
    const button = event.currentTarget as HTMLButtonElement;
    button.disabled = true; status.textContent = 'Loading the published weather snapshot…';
    try {
      const manifest = JSON.parse(await fetchText('data/manifest.json'));
      const path = manifest.spaceWeather?.path;
      if (typeof path !== 'string' || !/^artifacts\/space-weather-[a-f0-9]+\.json$/.test(path)
        || typeof manifest.release !== 'string') throw Error('Published weather reference unavailable.');
      const weather = JSON.parse(await fetchText(`data/${path}`));
      if (weather.schema !== 1 || !weather.solarWind || !weather.geomagnetic) throw Error('Weather format unavailable.');
      snapshot = snapshotTable(weather, manifest.release);
      main.querySelector('#delivery-weather-readings')!.replaceChildren(snapshot);
      status.textContent = 'Snapshot loaded. Save offline copy to include these dated readings. Nothing refreshes automatically.';
    } catch (error) { status.textContent = `Snapshot not loaded. ${String(error)}`; button.disabled = false; }
  });
  main.querySelector('#delivery-save')!.addEventListener('click', () => {
    const saved = new DOMParser().parseFromString(study, 'text/html');
    if (snapshot) saved.body.insertBefore(saved.importNode(snapshot, true), saved.body.querySelector('details'));
    main.querySelectorAll('[data-saved-visual]').forEach(node => {
      if (node.childNodes.length) {
        const copy=saved.importNode(node,true) as HTMLElement;
        // Offline links must still reach the online full-resolution artifact.
        copy.querySelectorAll('a[href]').forEach(a => {
          a.setAttribute('href',new URL(a.getAttribute('href')!,document.baseURI).href);
        });
        saved.body.insertBefore(copy,saved.body.querySelector('details'));
      }
    });
    const html = '<!doctype html>\n' + saved.documentElement.outerHTML;
    const blob = new Blob([html], { type:'text/html;charset=utf-8' });
    if (blob.size > DOCUMENT_LIMIT) { status.textContent = 'Offline copy exceeds the 4 MiB budget.'; return; }
    const href = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = href; link.download = 'space-study.html'; link.click();
    setTimeout(() => URL.revokeObjectURL(href), 10000);
    status.textContent = `Offline copy prepared (${blob.size.toLocaleString('en-US')} bytes). Save the file, then open it directly. It does not update itself.`;
  });
}

export function mountEntrance(loadFull = startFullExplorer, loadStudy = startStudy) {
  const entrance = document.getElementById('delivery-entrance');
  if (!entrance) return;
  const p = parsePreferences(readPreference());
  const hints = browserHints();
  const data = document.getElementById('delivery-data') as HTMLSelectElement;
  const display = document.getElementById('delivery-display') as HTMLSelectElement;
  const note = document.getElementById('delivery-mode-note')!;
  const button = document.getElementById('delivery-enter') as HTMLButtonElement;
  data.value = p.data; display.value = p.display;
  const update = () => {
    p.data = data.value as DeliveryPreferences['data']; p.display = display.value as DeliveryPreferences['display'];
    const study = deliveryMode(p,hints) === 'study';
    note.hidden = !study;
    note.textContent = 'Your selected or browser preference starts in static reading. You can open the interactive explorer at any time.';
  };
  data.addEventListener('change', update); display.addEventListener('change', update); update();
  let entering = false;
  const enter = async () => {
    if (entering) return;
    entering = true; button.disabled = true;
    p.entered = true; remember(p);
    document.getElementById('delivery-status')!.textContent = deliveryMode(p,hints) === 'study' ? 'Opening lessons…' : 'Loading explorer…';
    try { await (deliveryMode(p,hints) === 'study' ? loadStudy() : loadFull()); }
    catch (error) {
      const status = document.getElementById('delivery-status');
      if (status) status.textContent = `Could not open this view. ${String(error)} You can download the lessons below.`;
      entering = false; button.disabled = false;
    }
  };
  button.addEventListener('click', () => { void enter(); });
  document.getElementById('delivery-test')!.addEventListener('click', async event => {
    const test = event.currentTarget as HTMLButtonElement;
    const output = document.getElementById('delivery-test-result')!;
    test.disabled = true;
    output.textContent = 'Measuring one small request…';
    const connection = await runConnectionProbe(document.baseURI);
    const hardware = runHardwareSample();
    const nav = navigator as HintedNavigator;
    const reports = [nav.connection?.effectiveType && `connection type ${nav.connection.effectiveType}`,
      nav.connection?.downlink !== undefined && `downlink estimate ${nav.connection.downlink} Mb/s`,
      nav.deviceMemory !== undefined && `memory bucket ${nav.deviceMemory} GiB`,
      nav.hardwareConcurrency && `${nav.hardwareConcurrency} logical processors available`].filter(Boolean);
    output.textContent = `${connection} ${hardware}${reports.length ? ` Browser-reported hints (not measurements here): ${reports.join('; ')}.` : ''}`;
    // One sample per opening. Explicitly reopening options permits another.
  });
  const showOptions = new URL(location.href).searchParams.has('deliveryOptions');
  if (showOptions) (document.getElementById('delivery-options') as HTMLDetailsElement).open = true;
  else if (p.entered) void enter();
}

if (typeof document !== 'undefined') mountEntrance();
