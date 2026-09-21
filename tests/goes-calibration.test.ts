// @vitest-environment jsdom
import { expect, it } from "vitest";
import { satelliteFundamentalsPageView } from "../src/satellite-fundamentals";

it("C5: compares the correction to the old GOES value, not the unscaled value", () => {
  const factor = 0.7;
  expect(Math.round((1 - factor) * 100)).toBe(30);
  const increase = Math.round((1 / factor - 1) * 100);
  expect(increase).toBe(43);
  const correctedClass = (2.5 / factor).toFixed(1);
  expect(correctedClass).toBe("3.6");
  const document = new DOMParser().parseFromString(satelliteFundamentalsPageView("environment"), "text/html");
  const text = document.body.textContent!;
  expect(text).toContain("divide the old operational XRS-B value by 0.7");
  expect(text).toContain(`increasing it by about ${increase}%`);
  expect(text).toContain(`X${correctedClass}`);
  expect(text).toContain("Comparing flare magnitudes across that boundary without correcting is a real error");
  expect(text).not.toContain("42% smaller");
});
