/**
 * Asset imports.
 *
 * Vite treats .mp4 as a built-in asset type and rewrites the import to a
 * hashed URL under dist/assets, which is the directory deploy/web.Dockerfile
 * already copies wholesale. TypeScript needs telling, because this project
 * does not reference vite/client: the only other binary assets it ships are
 * the two typefaces, and those are reached through url() in styles.css rather
 * than through an import.
 */
declare module "*.mp4" {
  const src: string;
  export default src;
}

declare module "*.webp" {
  const src: string;
  export default src;
}

/**
 * WebVTT caption tracks. Not a Vite built-in asset type: a dynamic
 * `new URL(...vtt)` is left unresolved (the mechanisms captions shipped with
 * exactly that latent 404), so caption files are imported STATICALLY, which
 * assetsInclude in the vite configs turns into hashed dist/assets URLs.
 */
declare module "*.vtt" {
  const src: string;
  export default src;
}
