// Serves a built site folder under the GitHub Pages base path, like
// https://maxim75.github.io/sydney-travel-time/.
// Usage: node scripts/serve.mjs <dir> [port]
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const [dir = "out", port = process.env.PORT ?? "3000"] = process.argv.slice(2);
const root = resolve(dir), base = process.env.BASE_PATH ?? "/sydney-travel-time";
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".woff2": "font/woff2", ".txt": "text/plain", ".svg": "image/svg+xml", ".ico": "image/x-icon",
};

createServer(async (req, res) => {
  const { pathname } = new URL(req.url ?? "/", "http://localhost");
  if (pathname === "/" || pathname === base) { res.writeHead(302, { location: `${base}/` }); return res.end(); }
  if (!pathname.startsWith(`${base}/`)) { res.writeHead(404); return res.end("Not found"); }
  let path;
  try { path = join(root, normalize(decodeURIComponent(pathname.slice(base.length)))); }
  catch { res.writeHead(400); return res.end("Bad request"); }  // malformed percent-encoding
  if (path !== root && !path.startsWith(root + sep)) { res.writeHead(403); return res.end(); }
  try {
    if ((await stat(path)).isDirectory()) path = join(path, "index.html");
    const body = await readFile(path);
    res.writeHead(200, { "content-type": TYPES[extname(path)] ?? "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404); res.end("Not found");
  }
}).listen(Number(port), () => console.log(`Serving ${root} at http://localhost:${port}${base}/`));
