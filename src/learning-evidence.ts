/** The seven evidence classes have the same meaning on every learning route. */
export const EVIDENCE = {
  observed: 'Instrument or index value at a stated source and time; a point or index does not measure a global surface.',
  assimilated: 'Measurements combined with a model (numerical background); the resulting field includes inference.',
  model: 'Calculated state or relationship under stated assumptions; not a direct measurement. No measurement fixes any individual value shown here.',
  forecast: 'Estimate valid at a future time; identify both its issue time and valid time.',
  schematic: 'Teaching geometry or sequence; scale and motion are illustrative unless explicitly stated.',
  empirical: 'Relationship fitted to observations; its output is an estimate, not a new observation.',
  composite: 'Different evidence classes in one display; each component must state its own class.',
} as const;
export type Evidence = keyof typeof EVIDENCE;
export const evidenceNames = Object.keys(EVIDENCE).join(', ');
export function evidenceBadge(evidence: Evidence): string {
  return `<span class="layer-status ${evidence}">${evidence.toUpperCase()}</span>`;
}
export function evidenceGuide(): string {
  return `<details class="learning-evidence-guide"><summary>How to read the seven evidence classes</summary><p>A badge applies to the adjacent object, not every number on the page. A worked example is a qualifier, not an eighth class. Missing data remains missing.</p><dl>${Object.entries(EVIDENCE).map(([key, meaning]) => `<div><dt>${evidenceBadge(key as Evidence)}</dt><dd>${meaning}</dd></div>`).join('')}</dl></details>`;
}
export function legacyMediaNote(): string {
  return `<p class="media-evidence-note">Some archived frames use older labels: “illustration” means schematic, “model-derived” means model, and “measurement” means observed. These are qualifiers or older names, not extra evidence classes. Read the adjacent caption for which component each label describes.</p>`;
}
