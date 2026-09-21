// Static server for verification runs: serves the verify build at / and maps
// /data/ onto the real (unbundled) public/data directory.
//
// The dev server is not usable for this: additional git worktrees are kept
// inside the repo, so vite's watcher walks the whole ~77 GB data tree and
// reloads the page continuously.
import { createServer } from "node:http";
import { createReadStream, statSync } from "node:fs";
import { join, extname, normalize } from "node:path";

const DIST = process.argv[2];
const DATA = process.argv[3];
const PORT = Number(process.argv[4] ?? 5401);
const TYPES = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".woff2": "font/woff2", ".png": "image/png",
  ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp",
  ".mp4": "video/mp4",
  ".bin": "application/octet-stream", ".gz": "application/gzip",
};

const safe = (value) => normalize(value).replace(/^(\.\.(\/|\\|$))+/, "");

createServer((req, res) => {
  const path = decodeURIComponent(req.url.split("?")[0]);
  const file = path.startsWith("/data/")
    ? join(DATA, safe(path.slice(6)))
    : join(DIST, safe(path === "/" ? "/index.html" : path));
  try {
    const stat = statSync(file);
    if (stat.isDirectory()) { res.writeHead(404); return res.end("dir"); }
    res.writeHead(200, {
      "content-type": TYPES[extname(file)] ?? "application/octet-stream",
      "content-length": stat.size,
      "cache-control": "no-store",
    });
    createReadStream(file).pipe(res);
  } catch {
    res.writeHead(404);
    res.end("not found");
  }
}).listen(PORT, "127.0.0.1", () => console.log("serving", PORT, DIST, DATA));
