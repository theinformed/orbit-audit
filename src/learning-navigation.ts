/** Focus survives both replaced chapters and the weather track's hidden index. */
const openers = new WeakMap<HTMLElement, Map<string, { attribute: string; value: string }>>();
const attributes = ['data-fundamentals-page', 'data-layer-page', 'data-weather-lesson', 'data-weather-page'];

export function rememberChapterOpener(body: HTMLElement, track: string, candidate?: HTMLElement): void {
  const active = candidate ?? body.ownerDocument.activeElement;
  if (!(active instanceof HTMLElement) || !body.contains(active)) return;
  // Pager buttons are destinations, not the index door to restore.
  if (!active.closest('.fundamentals-index, .layer-index, #weather-index')) return;
  const attribute = attributes.find(name => active.hasAttribute(name));
  if (!attribute) return;
  const saved = openers.get(body) ?? new Map();
  saved.set(track, { attribute, value: active.getAttribute(attribute)! });
  openers.set(body, saved);
}

export function focusChapterHeading(root: HTMLElement): void {
  const heading = Array.from(root.querySelectorAll<HTMLElement>('h1, h2'))
    .find(node => !node.closest('[hidden]'));
  if (!heading) return;
  heading.tabIndex = -1;
  heading.focus({ preventScroll: true });
}

export function restoreChapterOpener(body: HTMLElement, track: string): void {
  const saved = openers.get(body)?.get(track);
  const opener = saved && Array.from(body.querySelectorAll<HTMLElement>(`[${saved.attribute}]`))
    .find(node => node.getAttribute(saved.attribute) === saved.value && !node.closest('[hidden]'));
  if (opener) opener.focus();
  else focusChapterHeading(body);
}

/** Local contents use buttons so section IDs never overwrite the route hash. */
export function mountLearningContents(body: HTMLElement): void {
  if (body.dataset.learningContentsBound) return;
  body.dataset.learningContentsBound = 'true';
  body.addEventListener('click', event => {
    const enlargement = (event.target as HTMLElement).closest<HTMLElement>('[data-figure-enlarge], [data-video-enlarge]');
    if (enlargement) {
      const figure = enlargement.closest('figure');
      const enlarged = figure?.classList.toggle('is-enlarged') ?? false;
      enlargement.setAttribute('aria-pressed', String(enlarged));
      return;
    }
    const button = (event.target as HTMLElement).closest<HTMLElement>('[data-learning-section]');
    if (!button) return;
    const section = body.ownerDocument.getElementById(button.dataset.learningSection!);
    if (!section || !body.contains(section)) return;
    section.closest('details')?.setAttribute('open', '');
    section.tabIndex = -1;
    section.focus({ preventScroll: true });
    section.scrollIntoView({ block: 'start', behavior: 'auto' });
  });
}
