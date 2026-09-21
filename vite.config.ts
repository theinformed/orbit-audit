import { defineConfig, loadEnv } from "vite";
import { constrainedDelivery } from "./tools/delivery-build";

export default defineConfig(({ mode }) => {
  const enabled = (process.env.VITE_CONSTRAINED_DELIVERY ?? loadEnv(mode, process.cwd()).VITE_CONSTRAINED_DELIVERY) === "true";
  return {
    // WebVTT caption tracks are real assets. Vite does not treat .vtt as an
    // asset type by default, so a `new URL("...vtt", import.meta.url)` was left
    // as a bare relative name that 404s in production — the mechanisms clips
    // shipped with exactly that latent break, found 2026-09-20 while wiring the
    // orbit-methods captions. One line cures the class for every lane.
    assetsInclude: ["**/*.vtt"],
  base: "./",
  plugins: [constrainedDelivery(enabled)],
  build: {
    target: enabled ? "es2018" : "es2022",
    sourcemap: false,
  },
  };
});
