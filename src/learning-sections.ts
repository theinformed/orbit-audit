/** Add local contents to rendered learning pages without changing route hashes. */
export function withLearningContents(html: string, prefix: string): string {
  let index = 0;
  const headings: { id: string; title: string }[] = [];
  const body = html.replace(/<h2([^>]*)>([\s\S]*?)<\/h2>/g, (_match, attributes: string, title: string) => {
    const id = attributes.match(/\bid="([^"]+)"/)?.[1] ?? `${prefix}-section-${++index}`;
    headings.push({ id, title: title.replace(/<[^>]*>/g, '') });
    return `<h2${attributes.includes('id="') ? attributes : `${attributes} id="${id}"`}>${title}</h2>`;
  });
  if (headings.length < 3) return body;
  const contents = `<nav class="learning-contents" aria-label="On this page"><p>On this page</p><ol>${headings.map(h => `<li><button type="button" class="link-button" data-learning-section="${h.id}">${h.title}</button></li>`).join('')}</ol></nav>`;
  return body.replace('</header>', `</header>${contents}`);
}
