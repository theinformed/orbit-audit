const checks: Record<string, [string, string]> = {
  link: ['A satellite is above your horizon. What else must be known before claiming the link closes?', 'The link budget needs antenna gain and pointing, transmitter power, receiver noise, frequency, bandwidth and propagation losses. Line of sight alone establishes none of those.'],
  spectrum: ['Can you assign a transmit frequency solely from an IEEE band letter?', 'No. Band letters organise frequency ranges. Service allocations, national rules and the actual authorised assignment determine which frequency may be used.'],
  orbits: ['A spacecraft is geosynchronous. Must it stay over one longitude?', 'No. A stationary ground position also needs the geostationary geometry: a circular, equatorial, prograde orbit. Inclination and eccentricity create ground motion.'],
  manoeuvre: ['After a brief prograde burn in a circular orbit, is the spacecraft immediately on a higher circular orbit?', 'No. The burn changes the orbit into an ellipse. Circularising at the higher altitude takes a further burn; the temporary local speed increase and the final circular speed answer different questions.'],
  spacecraft: ['Can a geometric footprint certify communications service throughout the circle?', 'No. Payload capability, beam pattern, pointing, power and the receiving terminal still constrain the service. A horizon footprint establishes line of sight.'],
  environment: ['A flare is observed now. Does that establish that CME plasma reaches Earth now?', 'No. Light, energetic particles and bulk plasma have different propagation and arrival times. Identify the messenger and valid time before choosing an operational response.'],
  inference: ['Does a change between two public element sets prove an operator performed a manoeuvre?', 'No. Fitting noise, element uncertainty and force-model differences can also change a propagated orbit. Treat the inference as conditional and retain the competing explanations.'],
  verdict: ['Can a historical stationkeeping pattern establish a spacecraft’s future mission or intent?', 'No. The observed history constrains a behavioural interpretation; it does not establish private intent or guarantee future actions. Keep confidence and missing evidence attached to the claim.'],
  dungey: ['Southward Bz and an auroral forecast arrive together. Are they two measurements of the same thing?', 'No. Bz is an upstream instrument quantity; an auroral product estimates precipitation from a model. Their locations, valid times and evidence classes remain distinct.'],
  engine: ['The selected time has no model cut. May a convincing surface fill that gap?', 'No. The missing cut is missing evidence. Another model may be shown only with its own class and assumptions; it cannot silently stand in for the unavailable product.'],
};
export function learningCheck(id: string): string {
  const check = checks[id];
  if (!check) return '';
  return `<details class="learning-check"><summary>Apply it: ${check[0]}</summary><p>${check[1]}</p></details>`;
}
