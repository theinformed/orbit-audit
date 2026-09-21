/**
 * Vite serves any file as a string when the import is suffixed `?raw`. Tests
 * use it to read `index.html` and `src/main.ts` as text, which is how the
 * reachability checks prove that a feature is actually referenced by the page
 * rather than merely present in the repository — the failure this project has
 * shipped three times. Declared here because the project deliberately carries
 * no Node type packages.
 */
declare module "*?raw" {
  const content: string;
  export default content;
}
