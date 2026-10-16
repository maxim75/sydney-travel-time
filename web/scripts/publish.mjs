// Replaces ../docs (served by GitHub Pages) with the static export in out/.
// Refuses to publish a build without its data, so the live site never loses its datasets.
import { cpSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const out = new URL("../out/", import.meta.url), docs = new URL("../../docs/", import.meta.url);
for (const path of ["index.html", "site.json", "map_data"]) {
  if (!existsSync(new URL(path, out))) {
    console.error(`out/${path} is missing: run \`uv run build_travel_time_map.py\` in the repository root, then this again.`);
    process.exit(1);
  }
}
if (!readFileSync(new URL("index.html", out), "utf8").includes("/sydney-travel-time/_next/")) {
  console.error("out/ was not built for the /sydney-travel-time base path (was BASE_PATH set?): run `npm run build` without it, then this again.");
  process.exit(1);
}
rmSync(docs, { recursive: true, force: true });
cpSync(out, docs, { recursive: true });
writeFileSync(new URL(".nojekyll", docs), "");  // GitHub Pages' Jekyll would otherwise drop the _next folder
console.log("Published web/out to docs/");
