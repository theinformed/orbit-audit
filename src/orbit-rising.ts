/** A reader surface over the drift artifact; no new detector or permission. */
import { DRIFT_COLOUR, driftControlText, driftObjectText, type DriftObject, type OrbitDriftBundle } from "./orbit-drift";

const count = (n: number) => n.toLocaleString("en-US");
const fitted = (o: DriftObject) => !o.gap && o.spanDays !== null && Number.isFinite(o.spanDays)
  && o.spanDays > 0 && o.slopeMetresPerDay !== null && Number.isFinite(o.slopeMetresPerDay);

function node<K extends keyof HTMLElementTagNameMap>(tag: K, text: string, className = ""): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  el.textContent = text;
  el.className = className;
  return el;
}

export function renderRisingNow(
  bundle: OrbitDriftBundle,
  names: ReadonlyMap<number, string>,
  onSelect: (norad: number) => void,
): HTMLElement {
  const panel = node("section", "", "orbit-history__status orbit-history__rising");
  panel.id = "orbit-history-rising-now";
  panel.tabIndex = -1;
  panel.style.borderLeftColor = DRIFT_COLOUR;
  panel.setAttribute("aria-label", "Rising now");
  panel.append(node("h3", "Rising now"));
  panel.append(node("p", `Drift artifact generated ${bundle.generatedAt}. These are long-window fits, not instantaneous motion or campaign start/end measurements.`, "orbit-history__provenance"));

  const measured = bundle.objects.filter(fitted).length;
  const gaps = bundle.objects.filter(o => !!o.gap).length;
  const rising = bundle.objects.filter(o => o.raising);
  const summary = node("div", "", "orbit-history__rising-coverage");
  summary.append(node("p", `${count(bundle.objects.length)} objects evaluated; ${count(measured)} fitted trends; ${count(gaps)} coverage gaps.`));
  if (bundle.controls.acceptance) summary.append(node("p", `Control result: ${bundle.controls.acceptance}.`));
  if (rising.length === 0) {
    const unmeasurable = measured === 0 || bundle.controls.passive.upper95 === null || bundle.controls.separation === null;
    summary.append(node("p", unmeasurable
      ? "Coverage is accumulating; this window’s controls cannot yet establish the raising population. Zero published rises is not evidence that no objects are climbing."
      : `The lane measured ${count(measured)} objects in this artifact; none currently sustains a resolved climb in its fitted window.`));
  }
  summary.append(node("p", "Station-keeping and short campaigns can escape this test. A coverage gap is not a measured absence of raising."));
  panel.append(summary);

  function section(title: string, rows: DriftObject[], outside: boolean): void {
    const group = node("section", "", "orbit-history__rising-group");
    group.append(node("h4", `${title} (${count(rows.length)})`));
    if (outside) group.append(node("p", "These rises are outside the drag regime. Their labels describe ambiguity, not demonstrated causes or propulsion claims."));
    if (!rows.length) group.append(node("p", "No resolved rises published in this section for this window."));
    else {
      const wrap = node("div", "", "orbit-history__table-wrap");
      const table = document.createElement("table");
      table.append(node("caption", `${title} — largest fitted slope first`));
      const header = table.createTHead().insertRow();
      for (const label of ["Object", "Slope m/day", "Span days", "Interpretation & warrant"]) {
        const th = node("th", label); th.scope = "col"; header.append(th);
      }
      const body = table.createTBody();
      const slope = (o: DriftObject) => o.slopeMetresPerDay !== null && Number.isFinite(o.slopeMetresPerDay) ? o.slopeMetresPerDay : -Infinity;
      for (const object of [...rows].sort((a, b) => slope(b) - slope(a) || a.norad - b.norad)) {
        const row = body.insertRow();
        const link = node("a", `${names.get(object.norad) || `NORAD ${object.norad}`} · ${object.norad}`);
        link.href = `#orbit-history-object-${object.norad}`;
        link.addEventListener("click", event => { event.preventDefault(); onSelect(object.norad); });
        row.insertCell().append(link);
        row.insertCell().textContent = Number.isFinite(slope(object)) ? `${slope(object) >= 0 ? "+" : ""}${slope(object).toFixed(2)}` : "Unavailable";
        row.insertCell().textContent = object.spanDays !== null && Number.isFinite(object.spanDays) && object.spanDays > 0 ? object.spanDays.toFixed(1) : "Unavailable";
        const claim = row.insertCell();
        driftObjectText(bundle, object).forEach(text => claim.append(node("p", text)));
      }
      wrap.append(table); group.append(wrap);
    }
    panel.append(group);
  }
  section("In the drag regime", rising.filter(o => o.inGate === true), false);
  section("Rising outside the drag regime", rising.filter(o => o.inGate === false), true);
  const unknown = rising.filter(o => o.inGate == null).length;
  if (unknown) panel.append(node("p", `${count(unknown)} published rises have no resolved regime; neither list assigns them one.`));
  const warrant = node("details", "");
  warrant.append(node("summary", "This window’s control and label warrant"));
  warrant.append(node("p", driftControlText(bundle)));
  panel.append(warrant);
  return panel;
}
