/** Preferences are choices, not diagnoses. Missing browser hints mean unknown. */
export type Choice = 'auto' | 'full' | 'light';
export interface DeliveryPreferences { data: Choice; display: Choice; entered: boolean }
export interface DeliveryHints { saveData?: boolean; reducedData?: boolean; reducedMotion?: boolean }
export const PREFERENCE_KEY = 'space-delivery-v1';
export const PROBE_BYTES = 16 * 1024;
export const PROBE_TIMEOUT_MS = 4000;
export const DOCUMENT_LIMIT = 4 * 1024 * 1024;

export function parsePreferences(value: string | null): DeliveryPreferences {
  try {
    const parsed = JSON.parse(value ?? '{}');
    const choice = (v: unknown): Choice => v === 'full' || v === 'light' ? v : 'auto';
    return { data: choice(parsed.data), display: choice(parsed.display), entered: parsed.entered === true };
  } catch { return { data: 'auto', display: 'auto', entered: false }; }
}

export function deliveryMode(p: DeliveryPreferences, hints: DeliveryHints): 'study' | 'full' {
  const lightData = p.data === 'light' || (p.data === 'auto' && (hints.saveData || hints.reducedData));
  const lightDisplay = p.display === 'light' || (p.display === 'auto' && hints.reducedMotion);
  return lightData || lightDisplay ? 'study' : 'full';
}

export function probeReport(bytes: number, elapsedMs: number): string {
  if (bytes !== PROBE_BYTES || !Number.isFinite(elapsedMs) || elapsedMs < 100) {
    return 'Sample too short or incomplete to estimate this connection. Choose either mode below.';
  }
  const speed = bytes / elapsedMs; // decimal KB/s
  return `Measured ~${Math.round(speed)} KB/s over ${(elapsedMs / 1000).toFixed(2)} s (${bytes.toLocaleString('en-US')} bytes). `
    + 'One small request, including latency; caches and shared traffic can skew it. '
    + (speed < 250 ? 'Starting with on-demand data may help. ' : 'This sample does not establish sustained speed. ')
    + 'Your settings have not changed.';
}

/** Bound decoded bodies too: Content-Length can describe compressed bytes or be absent. */
export async function boundedBody(response: Response, limit: number): Promise<Uint8Array> {
  if (!response.ok || response.redirected) {
    await response.body?.cancel().catch(() => {});
    throw Error(`Download unavailable (HTTP ${response.status}).`);
  }
  const size = Number(response.headers.get('content-length'));
  if (Number.isFinite(size) && size > limit) {
    await response.body?.cancel().catch(() => {});
    throw Error('Download exceeds its stated budget.');
  }
  if (!response.body) throw Error('This browser cannot read a bounded download. Use the study download link.');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > limit) throw Error('Download exceeds its stated budget.');
      chunks.push(value);
    }
  } catch (error) { await reader.cancel().catch(() => {}); throw error; }
  finally { reader.releaseLock(); }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

/** No call until an explicit click. One finite same-origin object; never a range request. */
export async function runConnectionProbe(base: string, fetcher: typeof fetch = fetch): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  const start = performance.now();
  try {
    const url = new URL('assets/delivery-probe.bin', base);
    url.searchParams.set('sample', String(Date.now()));
    const response = await fetcher(url, { cache: 'no-store', redirect: 'error', signal: controller.signal });
    const bytes = await boundedBody(response, PROBE_BYTES);
    return probeReport(bytes.length, performance.now() - start);
  } catch {
    return 'No usable connection measurement (blocked, timed out, or unavailable). This does not diagnose a slow link. Choose either mode below.';
  } finally { clearTimeout(timeout); }
}

/** A tiny CPU arithmetic sample, not a GPU benchmark. No canvases or workers. */
export function runHardwareSample(now: () => number = () => performance.now()): string {
  const start = now();
  let rounds = 0;
  let value = 1;
  let elapsed = 0;
  do {
    for (let i = 0; i < 1000; i++) value = (value * 1664525 + 1013904223) >>> 0;
    rounds += 1000;
    elapsed = now() - start;
  } while (rounds < 100000 && elapsed < 20);
  // Keep the result observable without retaining a benchmark payload.
  return `CPU sample: ${rounds.toLocaleString('en-US')} arithmetic steps in ~${elapsed.toFixed(1)} ms (checksum ${value}). `
    + 'Other work and timer precision affect this result. Graphics performance was not tested; use static reading if the globe struggles.';
}
