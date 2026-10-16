# Next.js + TypeScript Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-written `map_template.html` page with a TypeScript Next.js app. The app is exported as a static bundle into `docs/`, so GitHub Pages keeps serving it unchanged at https://maxim75.github.io/sydney-travel-time/. The Python data pipeline stays.

**Architecture:** A new `web/` folder holds a Next.js 16 App Router app with `output: "export"` and `basePath: "/sydney-travel-time"`. The Python build stops templating HTML. Instead it writes `web/public/site.json`, which was the payload embedded in `index.html` before, plus `web/public/map_data/<id>.json`, whose format is unchanged. The page fetches `site.json` at runtime. The canvas map is a framework-free `MapRenderer` class (a direct port of the existing drawing code) wrapped in one client component. The header, controls, legend, key, tooltip and suburb table become React components that share pure, unit-tested functions in `web/lib/`. `npm run publish-site` builds and copies `web/out/` into `docs/`.

**Tech Stack:** Next.js 16.4, React 19, TypeScript (strict), `next/font/google` (Barlow, Barlow Condensed), Vitest 4 (unit), Playwright 1.5x (end-to-end), Node 22. Python 3.12 + uv for the pipeline, unchanged.

**Spec:** There is no separate spec document. The requirements come from the conversation of 2026-10-16 ("convert the map to a TypeScript Next.js static export, keeping the Python pipeline; it must work as a static GitHub Pages site") and are listed under Global Constraints.

## Global Constraints

- Hosting stays as it is: GitHub Pages "Deploy from a branch", branch `main`, folder `/docs`, at `https://maxim75.github.io/sydney-travel-time/`. No repository settings change and no GitHub Actions.
- `basePath` is `/sydney-travel-time` (overridable with the `BASE_PATH` env var). Every asset and data URL must work under it.
- Static export only (`output: "export"`): no API routes, no server actions, no `next/image` optimisation, no middleware.
- TypeScript `strict: true`. `npm run typecheck` must pass.
- The Google Analytics ID stays `G-WDYB3WJ819`. The event name stays `hexagon_click`, with params `latitude`, `longitude` (degrees, 5 decimals), `suburb` and `dataset` (the selected dataset id).
- The localStorage key stays `sydney-travel-times:dataset`.
- `map_data/<id>.json` keeps its current schema. `site.json` is exactly the object that used to be embedded (`scale, total, localities, center, verts, loc, labels, datasets, transit`).
- Visual and behavioural parity with the current page: same CSS (tokens, class names, light/dark), same copy, same interactions (drag, wheel and pinch zoom, hover or tap tooltip, pinned tooltip on touch, suburb zoom, remembered dataset). No new features.
- The Python CLI (`build_travel_time_map.py` arguments and data collection) is unchanged except that `--site` now means "the folder the web app serves data from" and defaults to `web/public`.
- Generated data under `web/public/site.json` and `web/public/map_data/` is git-ignored. `docs/` remains the committed, published build output.

## Review Focus

1. **Project-site sub-path.** The page is served from `/sydney-travel-time/`, not `/`. Any URL built without the base path (fonts, `_next` chunks, `site.json`, `map_data`) 404s on Pages but may look fine in dev. Pinned by the "no failed requests under the base path" e2e test in Task 5.
2. **Hashed web-font family names on the canvas.** `next/font` renames font families, so canvas labels that hard-code `'Barlow Condensed'` silently fall back to Arial. The renderer must read `--cond` and `--sans` from CSS. Pinned by the "labels use Barlow" e2e test in Task 6.
3. **Dataset race.** Someone picks dataset B while dataset A (6 MB) is still downloading. A must not overwrite B when it arrives. Pinned by the "slow earlier dataset" e2e test in Task 5.
4. **`site.json` fails to load.** This is a new failure mode, because the data used to be inline. The page must say so instead of staying blank or throwing. Pinned by the "site data fails" e2e test in Task 5.
5. **Stale remembered dataset.** localStorage names a dataset that has since been removed, or localStorage throws (private mode). The page must fall back to the first dataset. Pinned by unit tests in Task 3 and an e2e test in Task 5.

---

## File Structure

```
web/
  package.json            scripts and dependencies
  tsconfig.json
  next.config.ts          static export, basePath, NEXT_PUBLIC_BASE_PATH
  vitest.config.ts        unit tests only (tests/unit)
  playwright.config.ts    e2e against the exported build served under the base path
  app/
    layout.tsx            <html>, fonts, Google Analytics, metadata
    page.tsx              renders <TravelMap/>
    globals.css           the CSS from map_template.html (font tokens point at next/font)
  components/
    TravelMap.tsx         loads site.json; owns dataset, metric, filter and lines state
    Header.tsx            eyebrow, title, subtitle, stats
    Controls.tsx          dataset picker, colour-by, filters, base map toggle
    MapCanvas.tsx         canvas + zoom buttons + key slot + tooltip; wraps MapRenderer
    MapKey.tsx            on-map colour key
    Tooltip.tsx           hexagon tooltip
    Legend.tsx            band counts below the map
    SuburbTable.tsx       searchable, sortable suburb table
    Credits.tsx           data credits footer
  lib/
    types.ts              SiteData, DatasetSummary, DatasetData, Overlay
    format.ts             fmt, km, mins
    data.ts               fetchJson, loadSite, loadDataset, emptyOverlay, pickInitialDataset
    storage.ts            rememberedDataset, rememberDataset (never throw)
    analytics.ts          hexagonClickParams, trackHexagonClick
    geometry.ts           COS, buildGeometry (world coordinates, hit testing)
    metrics.ts            metrics, filters, classify, hasMorning, labels
    stats.ts              median, headerStats, suburbRows, sortRows, classCounts
    renderer.ts           MapRenderer (canvas drawing, pan/zoom state, theme)
    pointer.ts            attachPointer (drag, pinch, wheel, hover, tap)
  scripts/
    serve.mjs             static server for a folder under the base path
    publish.mjs           copies out/ into ../docs (with .nojekyll)
  tests/
    fixtures.ts           a 7-hexagon site and two datasets, shared by unit and e2e tests
    unit/*.test.ts
    e2e/helpers.ts, page.spec.ts, map.spec.ts
build_travel_time_map.py  writes web/public/site.json instead of docs/index.html
map_template.html         deleted in Task 7
.claude/launch.json       previews docs/ under the base path; adds a Next dev server
```

---

### Task 1: Scaffold the Next.js app

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/vitest.config.ts`, `web/app/layout.tsx`, `web/app/page.tsx`, `web/app/globals.css`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `npm run build` → `web/out/` under basePath `/sydney-travel-time`. `process.env.NEXT_PUBLIC_BASE_PATH` is available to client code. The CSS variables `--sans` and `--cond` resolve to the next/font families.

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "sydney-travel-time-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "publish-site": "next build && node scripts/publish.mjs",
    "preview": "node scripts/serve.mjs out",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:e2e": "playwright test"
  }
}
```

- [ ] **Step 2: Install dependencies**

```bash
cd web && npm install next@16.4 react@19 react-dom@19 && npm install -D typescript @types/node @types/react @types/react-dom vitest
```

Expected: `package.json` gains `dependencies` and `devDependencies`, `package-lock.json` is created, and there are no peer-dependency errors.

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2023"],
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules", "out"]
}
```

(`next build` may rewrite a few of these fields. Keep its edits.)

- [ ] **Step 4: Create `web/next.config.ts`**

```ts
import type { NextConfig } from "next";

// GitHub Pages serves this project site from /sydney-travel-time/
const basePath = process.env.BASE_PATH ?? "/sydney-travel-time";

const config: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default config;
```

- [ ] **Step 5: Create `web/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { include: ["tests/unit/**/*.test.ts"], environment: "node" },
});
```

- [ ] **Step 6: Create `web/app/globals.css` from the existing page's styles**

```bash
cd web && sed -n '16,148p' ../map_template.html > app/globals.css
```

Then, in `web/app/globals.css`, replace these two lines:

```css
  --sans: "Barlow", "Helvetica Neue", Arial, sans-serif;
  --cond: "Barlow Condensed", "Arial Narrow", "Helvetica Neue", Arial, sans-serif;
```

with:

```css
  --sans: var(--font-barlow), "Helvetica Neue", Arial, sans-serif;
  --cond: var(--font-barlow-condensed), "Arial Narrow", "Helvetica Neue", Arial, sans-serif;
```

Check: `head -3 app/globals.css` starts with `:root {` and `tail -2 app/globals.css` ends with the `@media (max-width: 760px)` block's closing `}`.

- [ ] **Step 7: Create `web/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import "./globals.css";

const barlow = Barlow({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-barlow" });
const barlowCondensed = Barlow_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-barlow-condensed" });
const GA_ID = "G-WDYB3WJ819";

export const metadata: Metadata = { title: "Sydney Travel Times" };

export default function RootLayout({ children }: { children: ReactNode }) {
  // The font variables go on <html> so the :root tokens --sans and --cond can resolve them
  return (
    <html lang="en-AU" className={`${barlow.variable} ${barlowCondensed.variable}`}>
      <body>
        {children}
        <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
        <Script id="gtag-init" strategy="afterInteractive">
          {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
        </Script>
      </body>
    </html>
  );
}
```

- [ ] **Step 8: Create a placeholder `web/app/page.tsx`** (Task 5 replaces it)

```tsx
export default function Page() {
  return <div className="wrap"><h1>Sydney travel times</h1></div>;
}
```

- [ ] **Step 9: Ignore generated files.** Append to the repository `.gitignore`:

```
# Web app
web/node_modules/
web/.next/
web/out/
web/next-env.d.ts
web/test-results/
web/playwright-report/
web/public/site.json
web/public/map_data/
```

- [ ] **Step 10: Build and check the export**

Run: `cd web && npm run build && ls out && grep -o '/sydney-travel-time/_next/static/[^"]*\.css' out/index.html | head -1 && npm run typecheck`

Expected: the build succeeds and `out/` contains `index.html`, `404.html` and `_next/`. The grep prints one stylesheet path under `/sydney-travel-time/_next/`, and typecheck exits 0.

- [ ] **Step 11: Commit**

```bash
git add .gitignore web/package.json web/package-lock.json web/tsconfig.json web/next.config.ts web/vitest.config.ts web/app
git commit -m "Scaffold a Next.js static export app for the map"
```

---

### Task 2: Make the Python build write `site.json` for the web app

**Files:**
- Modify: `build_travel_time_map.py` (docstring lines 1-15, `TEMPLATE` line 32, `build_site` lines 182-194, `--site` argument line 213)

**Interfaces:**
- Produces: `web/public/site.json`, with keys `scale, total, localities, center, verts, loc, labels, datasets, transit`, and `web/public/map_data/<id>.json` (same schema as `docs/map_data/` today).

- [ ] **Step 1: Update the module docstring** (lines 1-15) to:

```python
"""Create travel time datasets and build the data the map web app shows.

With dataset parameters, creates (or resumes) the dataset for that building, date and
time, collects its journeys for every sampled hexagon, merges the results into its
dataset.json when complete, then rebuilds the site data. Without them, only rebuilds the site data.

The site data (default web/public/, served by the Next.js app in web/) is site.json, with
the hexagons, suburb labels, transit lines and the list of complete datasets, plus one compact
map_data/<id>.json per complete dataset that the page fetches when it is selected.
Publish the site to docs/ (GitHub Pages) with `npm run publish-site` in web/.

Usage:
    uv run build_travel_time_map.py
    caffeinate -is uv run build_travel_time_map.py --building GANSW706029353 --date 2026-10-12 --arrive-by 09:00
    caffeinate -is uv run build_travel_time_map.py --building GANSW706029353 --date 2026-10-10 --depart-at 21:00 [--max-wait-hours 3]
"""
```

- [ ] **Step 2: Delete the `TEMPLATE = ...` line** (line 32).

- [ ] **Step 3: Replace the end of `build_site`** (from `payload = json.dumps(...)` to the final `print`) with:

```python
    path = args.site / "site.json"
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB): {len(cells):,} hexagons, {len(complete)} datasets")
```

- [ ] **Step 4: Change the `--site` argument** to:

```python
    parser.add_argument("--site", type=Path, default=Path("web/public"),
                        help="Folder the map web app serves its data from (default: web/public)")
```

- [ ] **Step 5: Run the site build and check its output**

Run: `uv run build_travel_time_map.py && python3 -c "import json; d=json.load(open('web/public/site.json')); print(sorted(d), d['total'], [x['id'] for x in d['datasets']])" && ls web/public/map_data`

Expected: the output includes `Wrote web/public/map_data/GANSW706029353_2026-10-10_dep2100_w3h.json`, the `..._arr0900.json` file and `Wrote web/public/site.json (2.4 MB)`. Python prints `['center', 'datasets', 'labels', 'loc', 'localities', 'scale', 'total', 'transit', 'verts']`, the hexagon count and both dataset ids. `git status` shows `docs/` unchanged and nothing under `web/public` tracked.

- [ ] **Step 6: Commit**

```bash
git add build_travel_time_map.py
git commit -m "Write the map's site data as site.json for the web app"
```

---

### Task 3: Types, formatting, data loading, storage and analytics

**Files:**
- Create: `web/lib/types.ts`, `web/lib/format.ts`, `web/lib/data.ts`, `web/lib/storage.ts`, `web/lib/analytics.ts`, `web/tests/fixtures.ts`
- Test: `web/tests/unit/format.test.ts`, `web/tests/unit/data.test.ts`, `web/tests/unit/storage.test.ts`, `web/tests/unit/analytics.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `Direction`, `Building`, `DatasetSummary`, `Leg`, `DatasetData`, `Overlay`, `Label`, `Station`, `Transit`, `SiteData`
  - `format.ts`: `fmt(n: number): string`, `km(m: number): string`, `mins(m: number): string`
  - `data.ts`: `BASE_PATH: string`, `fetchJson<T>(path: string, fetchImpl?: FetchLike): Promise<T>`, `loadSite(fetchImpl?): Promise<SiteData>`, `loadDataset(id: string, fetchImpl?): Promise<DatasetData>`, `emptyOverlay(total: number): Overlay`, `pickInitialDataset(datasets: DatasetSummary[], saved: string | null): string | null`
  - `storage.ts`: `rememberedDataset(storage?: Storage | null): string | null`, `rememberDataset(id: string, storage?: Storage | null): void`
  - `analytics.ts`: `hexagonClickParams(site, i, dataset)`, `trackHexagonClick(site, i, dataset): void`
  - `tests/fixtures.ts`: `ONWARD_ID`, `RETURN_ID`, `fixtureSite(): SiteData`, `fixtureDataset(direction: Direction): DatasetData`

- [ ] **Step 1: Create `web/lib/types.ts`**

```ts
// Shapes of site.json and map_data/<id>.json, written by build_travel_time_map.py.
// Coordinates are integers in 1e-5 degrees: [longitude, latitude].

export type Direction = "onward" | "return";

export interface Building { name: string; address: string; xy: [number, number]; }

export interface DatasetSummary {
  id: string;
  direction: Direction;
  when: string;  // e.g. "9:00 on Mon 12 Oct 2026"
  label: string;
  maxWaitHours: number | null;  // return datasets only
  building: Building;
  counts: Record<string, number>;
  finished: string;
}

// [mode, route, minutes, metres, from, to]; mode indexes legModes, from and to index stops
export type Leg = [number, string, number, number, number, number];

// Per-hexagon columns, in site order. Status: 0 not computed, 1 ok, 2 no journey, 3 not found, 4 walk too far
export interface DatasetData extends DatasetSummary {
  status: number[];
  minutes: (number | null)[];  // onward: trip time; return: from the requested departure, including the wait
  trip?: (number | null)[];  // return only
  wait?: (number | null)[];  // return only
  morning?: number[];  // return only: 1 when the first trip leaves next morning
  walkMin: (number | null)[];
  walkM: (number | null)[];
  transports: (number | null)[];
  modes: number[];  // bits: 1 bus, 2 train/metro, 4 ferry, 8 light rail
  depart: string[];
  arrive: string[];
  address: string[];
  legs: (Leg[] | null)[];
  computed: number;
  legModes: string[];
  stops: string[];
}

// What the page draws: a loaded dataset, or an empty placeholder before one has loaded
export type Overlay = Omit<DatasetData, "id" | "label" | "counts" | "finished" | "building"> & { building: Building | null };

export type Label = [name: string, x: number, y: number, tier: number];
export type Station = [name: string, x: number, y: number, layer: string];
export interface Transit { lines: Record<string, number[][]>; stations: Station[]; }

export interface SiteData {
  scale: number;
  total: number;
  localities: string[];
  center: number[];  // x, y per hexagon
  verts: number[][];  // per hexagon: vertex offsets from its centre, x, y pairs
  loc: number[];  // per hexagon: index into localities
  labels: Label[];
  datasets: DatasetSummary[];
  transit: Transit | null;
}
```

- [ ] **Step 2: Create the shared test fixture `web/tests/fixtures.ts`**

```ts
import type { DatasetData, DatasetSummary, Direction, SiteData } from "../lib/types";

// Seven hexagons: one at the Queen Victoria Building's coordinates and a ring of six around it.
// Hexagon 0 is ok by train, 1 ok by bus, 2 ok walking only, 3 no journey, 4 walk too far,
// 5 not found, 6 not computed. Hexagons 0-2 and 6 are in Sydney, 3-5 in Haymarket.
export const ONWARD_ID = "TEST_2026-10-12_arr0900";
export const RETURN_ID = "TEST_2026-10-10_dep2100_w3h";
const BASE: [number, number] = [15120669, -3387174];
const R = 200;
const OFFSETS: [number, number][] = [[0, 0], ...Array.from({ length: 6 }, (_, j): [number, number] => {
  const a = Math.PI / 6 + (j * Math.PI) / 3;
  return [Math.round(Math.sqrt(3) * R * Math.cos(a)), Math.round(Math.sqrt(3) * R * Math.sin(a))];
})];
const HEX = Array.from({ length: 6 }, (_, j) => [
  Math.round(R * Math.cos((j * Math.PI) / 3)), Math.round(R * Math.sin((j * Math.PI) / 3)),
]).flat();

function summary(direction: Direction): DatasetSummary {
  const onward = direction === "onward";
  return {
    id: onward ? ONWARD_ID : RETURN_ID,
    direction,
    when: onward ? "9:00 on Mon 12 Oct 2026" : "21:00 on Sat 10 Oct 2026",
    label: onward ? "Test Building · to, arrive by 9:00 · Mon 12 Oct 2026"
      : "Test Building · from, leave at 21:00 (wait up to 3 h) · Sat 10 Oct 2026",
    maxWaitHours: onward ? null : 3,
    building: { name: "Test Building", address: "1 TEST STREET, SYDNEY NSW 2000", xy: BASE },
    counts: {},
    finished: "2026-09-27T07:55:09+10:00",
  };
}

export function fixtureSite(): SiteData {
  return {
    scale: 100_000,
    total: 7,
    localities: ["Haymarket", "Sydney"],
    center: OFFSETS.flatMap(([dx, dy]) => [BASE[0] + dx, BASE[1] + dy]),
    verts: OFFSETS.map(() => [...HEX]),
    loc: [1, 1, 1, 0, 0, 0, 1],
    labels: [["Sydney", BASE[0], BASE[1] + 300, 1]],
    datasets: [summary("onward"), summary("return")],
    transit: {
      lines: { rail: [[BASE[0] - 600, BASE[1], BASE[0] + 600, BASE[1]]] },
      stations: [["Town Hall Station", BASE[0], BASE[1], "rail"]],
    },
  };
}

export function fixtureDataset(direction: Direction): DatasetData {
  const night = direction === "return";
  const data: DatasetData = {
    ...summary(direction),
    status: [1, 1, 1, 2, 4, 3, 0],
    minutes: night ? [40, 200, 130, null, null, null, null] : [25, 50, 140, null, null, null, null],
    walkMin: [6, 12, 3, null, null, null, null],
    walkM: [450, 900, 200, null, null, null, null],
    transports: [1, 2, 0, null, null, null, null],
    modes: [2, 1, 0, 0, 0, 0, 0],
    depart: ["08:20", "07:30", "06:40", "", "", "", ""],
    arrive: ["08:45", "08:20", "09:00", "", "", "", ""],
    address: ["1 TEST STREET, SYDNEY", "2 TEST STREET, SYDNEY", "3 TEST STREET, SYDNEY",
      "4 TEST STREET, HAYMARKET", "5 TEST STREET, HAYMARKET", "6 TEST STREET, HAYMARKET", ""],
    legs: [
      [[0, "", 4, 300, 0, 1], [1, "T1", 15, 9000, 1, 2], [0, "", 6, 450, 2, 0]],
      [[2, "333", 40, 12000, 3, 4]],
      null, null, null, null, null,
    ],
    computed: 6,
    legModes: ["walk", "train", "bus"],
    stops: ["", "Central Station", "Town Hall Station", "Bondi Junction", "Railway Square"],
  };
  if (night) Object.assign(data, {
    trip: [35, 60, 125, null, null, null, null],
    wait: [5, 140, 5, null, null, null, null],
    morning: [0, 1, 0, 0, 0, 0, 0],
  });
  return data;
}
```

- [ ] **Step 3: Write the failing tests**

`web/tests/unit/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { fmt, km, mins } from "../../lib/format";

describe("format", () => {
  it("formats counts with Australian thousands separators", () => expect(fmt(18970)).toBe("18,970"));
  it("formats distances in metres below 1 km", () => expect(km(950)).toBe("950 m"));
  it("formats distances in km with one decimal from 1 km", () => expect(km(1234)).toBe("1.2 km"));
  it("formats durations under two hours in minutes", () => expect(mins(119)).toBe("119 min"));
  it("formats durations from two hours in hours and minutes", () => expect(mins(125)).toBe("2 h 5 min"));
});
```

`web/tests/unit/data.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { emptyOverlay, fetchJson, loadDataset, pickInitialDataset } from "../../lib/data";
import { fixtureSite, ONWARD_ID, RETURN_ID } from "../fixtures";

const respond = (status: number, body: unknown = {}) => async () => new Response(JSON.stringify(body), { status });

describe("data", () => {
  it("parses a successful response", async () => {
    expect(await fetchJson("site.json", respond(200, { total: 7 }))).toEqual({ total: 7 });
  });
  it("throws with the HTTP status on failure", async () => {
    await expect(fetchJson("site.json", respond(404))).rejects.toThrow("HTTP 404");
  });
  it("requests map_data/<encoded id>.json", async () => {
    const urls: string[] = [];
    await loadDataset("a b", async (url) => { urls.push(url); return new Response("{}"); });
    expect(urls).toEqual(["/map_data/a%20b.json"]);
  });
  it("builds an empty overlay with every hexagon not computed", () => {
    const o = emptyOverlay(3);
    expect(o.status).toEqual([0, 0, 0]);
    expect(o.building).toBeNull();
    expect(o.computed).toBe(0);
  });
  it("restores a remembered dataset that still exists", () => {
    expect(pickInitialDataset(fixtureSite().datasets, RETURN_ID)).toBe(RETURN_ID);
  });
  it("falls back to the first dataset when the remembered one is gone", () => {
    expect(pickInitialDataset(fixtureSite().datasets, "GONE")).toBe(ONWARD_ID);
    expect(pickInitialDataset(fixtureSite().datasets, null)).toBe(ONWARD_ID);
  });
  it("picks nothing when there are no datasets", () => expect(pickInitialDataset([], "x")).toBeNull());
});
```

`web/tests/unit/storage.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { rememberDataset, rememberedDataset } from "../../lib/storage";

const memory = () => {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) } as unknown as Storage;
};
const broken = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
} as unknown as Storage;

describe("storage", () => {
  it("round-trips the chosen dataset", () => {
    const s = memory();
    rememberDataset("abc", s);
    expect(rememberedDataset(s)).toBe("abc");
  });
  it("returns null when storage throws", () => expect(rememberedDataset(broken)).toBeNull());
  it("ignores storage that throws on write", () => expect(() => rememberDataset("abc", broken)).not.toThrow());
  it("returns null without storage", () => expect(rememberedDataset(null)).toBeNull());
});
```

`web/tests/unit/analytics.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { hexagonClickParams } from "../../lib/analytics";
import { fixtureSite, ONWARD_ID } from "../fixtures";

describe("analytics", () => {
  it("describes a clicked hexagon by its centre in degrees, suburb and dataset", () => {
    expect(hexagonClickParams(fixtureSite(), 0, ONWARD_ID)).toEqual({
      latitude: -33.87174, longitude: 151.20669, suburb: "Sydney", dataset: ONWARD_ID,
    });
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd web && npm test`
Expected: FAIL, because the modules `../../lib/format`, `data`, `storage` and `analytics` can't be resolved.

- [ ] **Step 5: Implement `web/lib/format.ts`**

```ts
export const fmt = (n: number) => n.toLocaleString("en-AU");
export const km = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`);
export const mins = (m: number) => (m >= 120 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
```

- [ ] **Step 6: Implement `web/lib/data.ts`**

```ts
import type { DatasetData, DatasetSummary, Overlay, SiteData } from "./types";

export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
type FetchLike = (url: string) => Promise<Response>;

export async function fetchJson<T>(path: string, fetchImpl: FetchLike = (url) => fetch(url)): Promise<T> {
  const res = await fetchImpl(`${BASE_PATH}/${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const loadSite = (fetchImpl?: FetchLike) => fetchJson<SiteData>("site.json", fetchImpl);
export const loadDataset = (id: string, fetchImpl?: FetchLike) =>
  fetchJson<DatasetData>(`map_data/${encodeURIComponent(id)}.json`, fetchImpl);

// Until a dataset has loaded, every hexagon is drawn as not computed
export const emptyOverlay = (total: number): Overlay => ({
  direction: "onward", building: null, when: "", maxWaitHours: null,
  status: new Array(total).fill(0), minutes: [], walkMin: [], walkM: [], transports: [], modes: [],
  depart: [], arrive: [], address: [], legs: [], computed: 0, legModes: [], stops: [],
});

export const pickInitialDataset = (datasets: DatasetSummary[], saved: string | null) =>
  datasets.some((d) => d.id === saved) ? saved : (datasets[0]?.id ?? null);
```

- [ ] **Step 7: Implement `web/lib/storage.ts`**

```ts
// The chosen dataset is remembered per viewer. Storage can be missing or throw (private
// windows, blocked site data), so reads and writes never fail.
const STORE_KEY = "sydney-travel-times:dataset";

function localStore(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

export function rememberedDataset(storage: Storage | null = localStore()): string | null {
  try { return storage?.getItem(STORE_KEY) ?? null; } catch { return null; }
}

export function rememberDataset(id: string, storage: Storage | null = localStore()): void {
  try { storage?.setItem(STORE_KEY, id); } catch { /* storage unavailable */ }
}
```

- [ ] **Step 8: Implement `web/lib/analytics.ts`**

```ts
import type { SiteData } from "./types";

declare global {
  interface Window { gtag?: (...args: unknown[]) => void; }
}

type Site = Pick<SiteData, "center" | "scale" | "localities" | "loc">;

export const hexagonClickParams = (site: Site, i: number, dataset: string) => ({
  latitude: +(site.center[2 * i + 1] / site.scale).toFixed(5),
  longitude: +(site.center[2 * i] / site.scale).toFixed(5),
  suburb: site.localities[site.loc[i]],
  dataset,
});

// Google Analytics event for a clicked or tapped hexagon
export function trackHexagonClick(site: Site, i: number, dataset: string): void {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  window.gtag("event", "hexagon_click", hexagonClickParams(site, i, dataset));
}
```

- [ ] **Step 9: Run the tests and typecheck**

Run: `cd web && npm test && npm run typecheck`
Expected: PASS (17 tests) and typecheck exits 0.

- [ ] **Step 10: Commit**

```bash
git add web/lib web/tests
git commit -m "Add the map's data types, loading, storage and analytics helpers"
```

---

### Task 4: Geometry, metrics and statistics

**Files:**
- Create: `web/lib/geometry.ts`, `web/lib/metrics.ts`, `web/lib/stats.ts`
- Test: `web/tests/unit/geometry.test.ts`, `web/tests/unit/metrics.test.ts`, `web/tests/unit/stats.test.ts`

**Interfaces:**
- Consumes: `Overlay`, `SiteData` (Task 3), `fixtureSite`, `fixtureDataset` (Task 3)
- Produces:
  - `geometry.ts`: `COS: number`, `interface Geometry { n; cx: Float64Array; cy: Float64Array; start: Uint32Array; P: Float64Array; R: number; minX; maxX; minY; maxY; cellAt(X: number, Y: number): number }`, `buildGeometry(site): Geometry`
  - `metrics.ts`: `type MetricName = "time" | "walk" | "rides"`, `type FilterName = "all" | "train" | "bus" | "ferry" | "tram" | "tonight" | "morning"`, `interface Metric`, `CLS`, `CLASS_COUNT`, `WALK_LIMIT`, `TOO_FAR`, `isReturn(o)`, `hasMorning(o)`, `placeName(o)`, `noTripLabel(o)`, `metricOf(name, o): Metric`, `classify(o, metric, filter, n): Uint8Array`
  - `stats.ts`: `median(a: number[]): number | null`, `interface HeaderStats`, `headerStats(o, n)`, `interface SuburbRow`, `suburbRows(site, o): SuburbRow[]`, `type SortKey`, `defaultDir(key): 1 | -1`, `sortRows(rows, query, key, dir)`, `classCounts(cls): number[]`

- [ ] **Step 1: Write the failing tests**

`web/tests/unit/geometry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildGeometry, COS } from "../../lib/geometry";
import { fixtureSite } from "../fixtures";

describe("geometry", () => {
  const g = buildGeometry(fixtureSite());
  it("keeps six vertices per hexagon", () => {
    expect(g.n).toBe(7);
    expect(g.start[7]).toBe(42);
  });
  it("measures the circumradius in world units (x scaled by cos latitude)", () => {
    expect(g.R).toBeCloseTo(200 * COS, 5);
  });
  it("finds the hexagon under a point", () => {
    expect(g.cellAt(g.cx[0], g.cy[0])).toBe(0);
    expect(g.cellAt(g.cx[3] + 1, g.cy[3] - 1)).toBe(3);
  });
  it("finds nothing far from every hexagon", () => expect(g.cellAt(g.cx[0] + 5000, g.cy[0])).toBe(-1));
  it("bounds every centre", () => {
    expect(g.minX).toBe(Math.min(...g.cx));
    expect(g.maxY).toBe(Math.max(...g.cy));
  });
});
```

`web/tests/unit/metrics.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { classify, hasMorning, metricOf } from "../../lib/metrics";
import { fixtureDataset } from "../fixtures";

const onward = fixtureDataset("onward"), night = fixtureDataset("return");

describe("metrics", () => {
  it("bands journey times by their upper bounds", () => {
    const M = metricOf("time", onward);
    expect([M.band(30), M.band(31), M.band(150), M.band(151)]).toEqual([0, 1, 8, 9]);
    expect([M.labels[0], M.labels[1], M.labels[9]]).toEqual(["30 min or less", "31–45 min", "Over 150 min"]);
  });
  it("uses the time-to-get-there scale for return datasets", () => {
    expect(metricOf("time", night).title).toBe("Time to get there");
    expect(metricOf("walk", night).title).toBe("Walking time");
  });
  it("spreads rides over the ramp and caps them at five", () => {
    const M = metricOf("rides", onward);
    expect([M.band(0), M.band(1), M.band(7)]).toEqual([0, 2, 9]);
  });
  it("classifies every hexagon by status and journey time", () => {
    expect([...classify(onward, "time", "all", 7)]).toEqual([3, 5, 11, 1, 14, 2, 0]);
  });
  it("greys out trips the filter leaves out, and every non-trip", () => {
    expect([...classify(onward, "time", "train", 7)]).toEqual([3, 0, 0, 0, 0, 0, 0]);
    expect([...classify(onward, "time", "bus", 7)]).toEqual([0, 5, 0, 0, 0, 0, 0]);
  });
  it("shows next-morning trips apart in return datasets", () => {
    expect([...classify(night, "time", "all", 7)]).toEqual([4, 13, 9, 1, 14, 2, 0]);
    expect([...classify(night, "time", "tonight", 7)]).toEqual([4, 0, 9, 0, 0, 0, 0]);
  });
  it("knows which datasets have next-morning trips", () => {
    expect(hasMorning(night)).toBe(true);
    expect(hasMorning(onward)).toBe(false);
  });
});
```

`web/tests/unit/stats.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { classCounts, headerStats, median, sortRows, suburbRows, type SuburbRow } from "../../lib/stats";
import { fixtureDataset, fixtureSite } from "../fixtures";

describe("stats", () => {
  it("takes the median, rounding between the middle two", () => {
    expect([median([]), median([3]), median([1, 2]), median([1, 2, 3])]).toEqual([null, 3, 2, 2]);
  });
  it("summarises an onward dataset", () => {
    expect(headerStats(fixtureDataset("onward"), 7)).toEqual({
      computed: 6, pct: 6 / 7, median: 50, fastest: 25, morning: 0, tooFar: 1, noJourney: 1,
    });
  });
  it("leaves next-morning trips out of the return summary", () => {
    expect(headerStats(fixtureDataset("return"), 7)).toMatchObject({ median: 85, fastest: 40, morning: 1 });
  });
  it("lists suburbs with at least one trip", () => {
    expect(suburbRows(fixtureSite(), fixtureDataset("onward"))).toEqual([{
      name: "Sydney", total: 4, cells: [0, 1, 2, 6], done: 3, median: 50, fastest: 25, trainShare: 1 / 3,
    }]);
  });
  it("filters suburbs by a case-insensitive search", () => {
    const rows = suburbRows(fixtureSite(), fixtureDataset("onward"));
    expect(sortRows(rows, "SYD", "median", 1)).toHaveLength(1);
    expect(sortRows(rows, "hay", "median", 1)).toHaveLength(0);
  });
  it("sorts by the key in either direction, then by name", () => {
    const row = (name: string, median: number) => ({ name, median, fastest: 0, trainShare: 0, done: 0, total: 0, cells: [] }) as SuburbRow;
    const rows = [row("B", 10), row("C", 5), row("A", 10)];
    expect(sortRows(rows, "", "median", 1).map((r) => r.name)).toEqual(["C", "A", "B"]);
    expect(sortRows(rows, "", "median", -1).map((r) => r.name)).toEqual(["A", "B", "C"]);
  });
  it("counts hexagons per class", () => {
    const counts = classCounts(new Uint8Array([3, 3, 0, 14]));
    expect(counts).toHaveLength(15);
    expect([counts[0], counts[3], counts[14]]).toEqual([1, 2, 1]);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web && npm test`
Expected: FAIL, because `lib/geometry`, `lib/metrics` and `lib/stats` can't be resolved.

- [ ] **Step 3: Implement `web/lib/geometry.ts`**

```ts
import type { SiteData } from "./types";

// World units: 1e-5 degrees, x scaled by cos(latitude) so the map isn't stretched, y pointing down
export const COS = Math.cos((-33.87 * Math.PI) / 180);

export interface Geometry {
  n: number;
  cx: Float64Array;  // hexagon centres
  cy: Float64Array;
  start: Uint32Array;  // hexagon i's vertices are P[2 * start[i]] up to P[2 * start[i + 1]]
  P: Float64Array;
  R: number;  // hexagon circumradius
  minX: number; maxX: number; minY: number; maxY: number;
  cellAt(X: number, Y: number): number;  // hexagon within R of a world point, or -1
}

export function buildGeometry(site: Pick<SiteData, "total" | "center" | "verts">): Geometry {
  const N = site.total;
  const cx = new Float64Array(N), cy = new Float64Array(N), start = new Uint32Array(N + 1);
  const pts: number[] = [];
  for (let i = 0; i < N; i++) {
    const X = site.center[2 * i] * COS, Y = -site.center[2 * i + 1], v = site.verts[i];
    cx[i] = X; cy[i] = Y; start[i] = pts.length / 2;
    for (let j = 0; j < v.length; j += 2) pts.push(X + v[j] * COS, Y - v[j + 1]);
  }
  start[N] = pts.length / 2;
  const P = Float64Array.from(pts);
  const R = Math.hypot(P[0] - cx[0], P[1] - cy[0]);
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < N; i++) {
    minX = Math.min(minX, cx[i]); maxX = Math.max(maxX, cx[i]);
    minY = Math.min(minY, cy[i]); maxY = Math.max(maxY, cy[i]);
  }

  // spatial buckets for hover
  const G = R * 2, grid = new Map<string, number[]>();
  for (let i = 0; i < N; i++) {
    const key = Math.floor(cx[i] / G) + "," + Math.floor(cy[i] / G);
    let bucket = grid.get(key);
    if (!bucket) grid.set(key, (bucket = []));
    bucket.push(i);
  }
  function cellAt(X: number, Y: number): number {
    const gx = Math.floor(X / G), gy = Math.floor(Y / G);
    let best = -1, bd = R * R;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
      for (const i of grid.get(gx + a + "," + (gy + b)) ?? []) {
        const d = (cx[i] - X) ** 2 + (cy[i] - Y) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
    }
    return best;
  }

  return { n: N, cx, cy, start, P, R, minX, maxX, minY, maxY, cellAt };
}
```

- [ ] **Step 4: Implement `web/lib/metrics.ts`**

```ts
import type { Overlay } from "./types";

export type MetricName = "time" | "walk" | "rides";
export type FilterName = "all" | "train" | "bus" | "ferry" | "tram" | "tonight" | "morning";

export interface Metric {
  title: string;
  key: string;  // heading of the on-map key
  steps: number[];  // ramp steps (0-9) the metric uses
  band: (v: number) => number;  // ramp step to colour a value with
  labels: string[];  // one per step
  ticks?: number[];  // band boundaries, for the key
  short?: string[];  // one per step, for the key when there are no ticks
  value: (o: Overlay, i: number) => number;
}

// Class per hexagon: 0 ghost, 1 no journey, 2 not found, 3..12 ramp steps 0-9, 13 only next morning,
// 14 stop too far to walk to
export const CLS = { ghost: 0, noJourney: 1, notFound: 2, ramp: 3, morning: 13, tooFar: 14 } as const;
export const CLASS_COUNT = 15;

export const WALK_LIMIT = "1.2 km";
export const TOO_FAR = `Stop too far (>${WALK_LIMIT} walk)`;

export const isReturn = (o: Pick<Overlay, "direction">) => o.direction === "return";
export const hasMorning = (o: Overlay) => isReturn(o) && !!o.morning?.some(Boolean);
export const placeName = (o: Overlay) => o.building?.name ?? "the building";
export const noTripLabel = (o: Overlay) => `No trip within ${o.maxWaitHours} h`;  // return datasets only wait this long

// Bands from upper bounds: a value goes in the first band whose bound it doesn't exceed, else the last
const bounded = (bounds: number[], unit: string, over: string) => ({
  steps: bounds.map((_, b) => b).concat(bounds.length),
  band: (v: number) => { const b = bounds.findIndex((x) => v <= x); return b < 0 ? bounds.length : b; },
  labels: bounds.map((x, b) => (b ? `${bounds[b - 1] + 1}–${x} ${unit}` : `${x} ${unit} or less`)).concat(over),
  ticks: bounds,
});
const RIDE_STEPS = [0, 2, 4, 5, 7, 9];  // six values spread over the ten-step ramp

const METRICS: Record<MetricName, Metric> = {
  time: { title: "Journey time", key: "Journey time, minutes", value: (o, i) => o.minutes[i] ?? 0,
    ...bounded([30, 45, 60, 75, 90, 105, 120, 135, 150], "min", "Over 150 min") },
  walk: { title: "Walking time", key: "Walking time, minutes", value: (o, i) => o.walkMin[i] ?? 0,
    ...bounded([5, 8, 10, 12, 15, 20, 25, 30, 40], "min", "Over 40 min") },
  rides: { title: "Rides taken", key: "Rides taken", value: (o, i) => o.transports[i] ?? 0,
    steps: RIDE_STEPS, band: (v) => RIDE_STEPS[Math.min(v, 5)],
    labels: ["Walk only", "1 ride", "2 rides", "3 rides", "4 rides", "5 or more"],
    short: ["Walk", "1", "2", "3", "4", "5+"] },
};
const NIGHT_TIME: Metric = { title: "Time to get there", key: "Minutes from leaving, including the wait",
  value: (o, i) => o.minutes[i] ?? 0,
  ...bounded([30, 45, 60, 75, 90, 120, 150, 180, 240], "min", "Over 4 hours") };

export const metricOf = (name: MetricName, o: Pick<Overlay, "direction">): Metric =>
  name === "time" && isReturn(o) ? NIGHT_TIME : METRICS[name];

const FILTERS: Record<FilterName, (o: Overlay, i: number) => boolean> = {
  all: () => true,
  train: (o, i) => (o.modes[i] & 2) > 0,
  bus: (o, i) => o.modes[i] === 1,
  ferry: (o, i) => (o.modes[i] & 4) > 0,
  tram: (o, i) => (o.modes[i] & 8) > 0,
  tonight: (o, i) => !o.morning?.[i],
  morning: (o, i) => o.morning?.[i] === 1,
};

export function classify(o: Overlay, metric: MetricName, filter: FilterName, n: number): Uint8Array {
  const M = metricOf(metric, o), F = FILTERS[filter], cls = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const s = o.status[i];
    // journey time for places with no service until morning would just say "hours": show them apart
    if (s === 1 && F(o, i)) cls[i] = metric === "time" && o.morning?.[i] ? CLS.morning : CLS.ramp + M.band(M.value(o, i));
    else if (filter === "all" && s === 2) cls[i] = CLS.noJourney;
    else if (filter === "all" && s === 3) cls[i] = CLS.notFound;
    else if (filter === "all" && s === 4) cls[i] = CLS.tooFar;
    else cls[i] = CLS.ghost;
  }
  return cls;
}
```

- [ ] **Step 5: Implement `web/lib/stats.ts`**

```ts
import { CLASS_COUNT, isReturn } from "./metrics";
import type { Overlay, SiteData } from "./types";

export const median = (a: number[]): number | null =>
  a.length ? (a.length % 2 ? a[(a.length - 1) / 2] : Math.round((a[a.length / 2 - 1] + a[a.length / 2]) / 2)) : null;

export interface HeaderStats {
  computed: number; pct: number; median: number | null; fastest: number | null;
  morning: number; tooFar: number; noJourney: number;
}

// Trips that only leave next morning are left out of the medians and the fastest time
export function headerStats(o: Overlay, n: number): HeaderStats {
  const night = isReturn(o), ok: number[] = [];
  for (let i = 0; i < n; i++) if (o.status[i] === 1 && !(night && o.morning?.[i])) ok.push(o.minutes[i] ?? 0);
  ok.sort((a, b) => a - b);
  return {
    computed: o.computed, pct: o.computed / n, median: median(ok), fastest: ok.length ? ok[0] : null,
    morning: night ? (o.morning ?? []).reduce((a, b) => a + b, 0) : 0,
    tooFar: o.status.filter((s) => s === 4).length,
    noJourney: o.status.filter((s) => s === 2).length,
  };
}

export interface SuburbRow {
  name: string; total: number; cells: number[]; done: number; median: number; fastest: number; trainShare: number;
}

export function suburbRows(site: Pick<SiteData, "total" | "loc" | "localities">, o: Overlay): SuburbRow[] {
  const sub = new Map<number, { name: string; mins: number[]; train: number; cells: number[]; total: number }>();
  for (let i = 0; i < site.total; i++) {
    const l = site.loc[i];
    let r = sub.get(l);
    if (!r) sub.set(l, (r = { name: site.localities[l], mins: [], train: 0, cells: [], total: 0 }));
    r.total++; r.cells.push(i);
    if (o.status[i] === 1 && !o.morning?.[i]) { r.mins.push(o.minutes[i] ?? 0); if (o.modes[i] & 2) r.train++; }
  }
  return [...sub.values()].filter((r) => r.mins.length).map((r) => {
    r.mins.sort((a, b) => a - b);
    return { name: r.name, total: r.total, cells: r.cells, done: r.mins.length,
      median: median(r.mins)!, fastest: r.mins[0], trainShare: r.train / r.mins.length };
  });
}

export type SortKey = "name" | "median" | "fastest" | "train" | "done";
export const defaultDir = (key: SortKey): 1 | -1 => (key === "name" || key === "median" || key === "fastest" ? 1 : -1);

const SORT_VALUE: Record<SortKey, (r: SuburbRow) => string | number> = {
  name: (r) => r.name, median: (r) => r.median, fastest: (r) => r.fastest, train: (r) => r.trainShare, done: (r) => r.done,
};

export function sortRows(rows: SuburbRow[], query: string, key: SortKey, dir: 1 | -1): SuburbRow[] {
  const q = query.trim().toLowerCase(), value = SORT_VALUE[key];
  return rows.filter((r) => !q || r.name.toLowerCase().includes(q)).sort((a, b) => {
    const x = value(a), y = value(b);
    return (x < y ? -1 : x > y ? 1 : 0) * dir || a.name.localeCompare(b.name);
  });
}

export function classCounts(cls: Uint8Array): number[] {
  const counts = new Array<number>(CLASS_COUNT).fill(0);
  for (const c of cls) counts[c]++;
  return counts;
}
```

- [ ] **Step 6: Run the tests and typecheck**

Run: `cd web && npm test && npm run typecheck`
Expected: PASS (36 tests) and typecheck exits 0.

- [ ] **Step 7: Commit**

```bash
git add web/lib web/tests
git commit -m "Port the map's geometry, colour bands and suburb statistics to TypeScript"
```

---

### Task 5: The page without the canvas, plus end-to-end tests

**Files:**
- Create: `web/components/TravelMap.tsx`, `Header.tsx`, `Controls.tsx`, `Legend.tsx`, `MapKey.tsx`, `SuburbTable.tsx`, `Credits.tsx`, `web/scripts/serve.mjs`, `web/playwright.config.ts`, `web/tests/e2e/helpers.ts`, `web/tests/e2e/page.spec.ts`
- Modify: `web/app/page.tsx`

**Interfaces:**
- Consumes: everything from Tasks 3-4.
- Produces:
  - `TravelMap` (default export, client component, no props)
  - `MapKey({ metricName: MetricName; filter: FilterName; overlay: Overlay; showLines: boolean })`
  - `scripts/serve.mjs <dir> [port]`, which serves `<dir>` at `http://localhost:<port>/sydney-travel-time/` (env `BASE_PATH` overrides the prefix)
  - `tests/e2e/helpers.ts`: `serveFixtures(page, opts?)`, `failedRequests(page): string[]`

- [ ] **Step 1: Install Playwright**

```bash
cd web && npm install -D @playwright/test && npx playwright install chromium
```

(This downloads the Chromium test build, about 150 MB, from Playwright's CDN.)

- [ ] **Step 2: Create `web/scripts/serve.mjs`**

```js
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
  let path = join(root, normalize(decodeURIComponent(pathname.slice(base.length))));
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
```

- [ ] **Step 3: Create `web/playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test";

// Tests run against the static export, served under the same base path as GitHub Pages
const PORT = 4173;
const URL = `http://localhost:${PORT}/sydney-travel-time/`;

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: URL },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && node scripts/serve.mjs out ${PORT}`,
    url: URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
```

- [ ] **Step 4: Create `web/tests/e2e/helpers.ts`**

```ts
import type { Page } from "@playwright/test";
import { fixtureDataset, fixtureSite, ONWARD_ID, RETURN_ID } from "../fixtures";

interface Options {
  siteStatus?: number;  // respond to site.json with this error status
  delay?: Record<string, number>;  // milliseconds to hold back a dataset's response
}

// Answers site.json and map_data/<id>.json with the test fixtures, and blocks Google's tag script
export async function serveFixtures(page: Page, opts: Options = {}) {
  await page.route("https://www.googletagmanager.com/**", (route) => route.abort());
  await page.route("**/site.json", (route) =>
    opts.siteStatus ? route.fulfill({ status: opts.siteStatus }) : route.fulfill({ json: fixtureSite() }));
  await page.route("**/map_data/*.json", async (route) => {
    const id = decodeURIComponent(new URL(route.request().url()).pathname.split("/").pop()!.replace(/\.json$/, ""));
    const data = id === ONWARD_ID ? fixtureDataset("onward") : id === RETURN_ID ? fixtureDataset("return") : null;
    const wait = opts.delay?.[id];
    if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
    await (data ? route.fulfill({ json: data }) : route.fulfill({ status: 404 }));
  });
}

// Failed responses under the base path (the browser's own /favicon.ico probe is outside it),
// collected for the life of the page
export function failedRequests(page: Page): string[] {
  const failed: string[] = [];
  page.on("response", (res) => {
    if (res.status() >= 400 && new URL(res.url()).pathname.startsWith("/sydney-travel-time/")) failed.push(`${res.status()} ${res.url()}`);
  });
  return failed;
}
```

- [ ] **Step 5: Write the failing end-to-end tests in `web/tests/e2e/page.spec.ts`**

```ts
import { expect, test } from "@playwright/test";
import { fixtureSite, RETURN_ID } from "../fixtures";
import { failedRequests, serveFixtures } from "./helpers";

const [ONWARD_LABEL, RETURN_LABEL] = fixtureSite().datasets.map((d) => d.label);

test("loads every asset and the data under the base path", async ({ page }) => {
  const failed = failedRequests(page);
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("How long does it take to get to Test Building?");
  expect(failed).toEqual([]);
});

test("shows the first dataset's statistics", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  const stats = page.locator(".stats");
  await expect(stats).toContainText("6 of 7");
  await expect(stats).toContainText("50 min");
  await expect(stats).toContainText("with no journey found");
});

test("switching to a return dataset retitles the page and offers night filters", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("button", { name: "Tonight" })).toBeHidden();
  await page.getByLabel("Dataset").selectOption({ label: RETURN_LABEL });
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("How long does it take to get home from Test Building?");
  await expect(page.getByRole("button", { name: "Tonight" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Time to get there" })).toBeVisible();
  await page.getByRole("button", { name: "Next morning" }).click();
  await page.getByLabel("Dataset").selectOption({ label: ONWARD_LABEL });
  await expect(page.getByRole("button", { name: "All trips" })).toHaveAttribute("aria-pressed", "true");
});

test("the legend follows the colour-by choice", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  await page.getByRole("button", { name: "Rides" }).click();
  await expect(page.locator("#legend-title")).toHaveText("Rides taken");
  await expect(page.locator(".key")).toContainText("Rides taken");
});

test("the suburb table searches and sorts", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  const rows = page.locator(".tablebox tbody");
  await expect(rows).toContainText("Sydney");
  await page.getByLabel("Find a suburb").fill("hay");
  await expect(rows).toContainText("No suburb matches that search.");
  await page.getByLabel("Find a suburb").fill("");
  await page.getByRole("button", { name: "Suburb", exact: true }).click();
  await expect(page.getByRole("button", { name: "Suburb", exact: true })).toHaveAttribute("aria-sort", "ascending");
});

test("a slow earlier dataset does not replace a later pick", async ({ page }) => {
  await serveFixtures(page, { delay: { [fixtureSite().datasets[0].id]: 1500 } });
  await page.goto("./");
  await page.getByLabel("Dataset").selectOption({ label: RETURN_LABEL });
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await page.waitForTimeout(2000);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await expect(page.getByLabel("Dataset")).toHaveValue(RETURN_ID);
});

test("restores the remembered dataset, and ignores one that no longer exists", async ({ page }) => {
  await serveFixtures(page);
  await page.addInitScript((id) => localStorage.setItem("sydney-travel-times:dataset", id), RETURN_ID);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await page.evaluate(() => localStorage.setItem("sydney-travel-times:dataset", "GONE"));
  await page.addInitScript(() => localStorage.setItem("sydney-travel-times:dataset", "GONE"));
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get to Test Building");
});

test("says so when the site data can't be loaded", async ({ page }) => {
  await serveFixtures(page, { siteStatus: 404 });
  await page.goto("./");
  await expect(page.locator(".sub")).toHaveText("Couldn't load the map data (HTTP 404).");
});
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd web && npm run test:e2e`
Expected: FAIL. The placeholder page has no "How long does it take…" heading, no `.stats`, and no "Dataset" control.

- [ ] **Step 7: Create `web/components/Header.tsx`**

```tsx
import { fmt } from "../lib/format";
import { isReturn, WALK_LIMIT } from "../lib/metrics";
import { headerStats } from "../lib/stats";
import type { Overlay } from "../lib/types";

export default function Header({ o, n, hasDatasets }: { o: Overlay; n: number; hasDatasets: boolean }) {
  const night = isReturn(o), b = o.building, s = headerStats(o, n);
  const title = !b ? "Sydney travel times"
    : night ? `How long does it take to get home from ${b.name}?` : `How long does it take to get to ${b.name}?`;
  const sub = !b
    ? (hasDatasets ? "Loading the dataset…" : "No datasets have been built yet.")
    : night
    ? `Earliest public transport trip from ${b.name} (${b.address}) to each part of Greater Sydney, leaving at ${o.when}. ` +
      `Times include waiting there for the first service, up to ${o.maxWaitHours} hours; places with no departure in that time count as no trip.`
    : `Fastest public transport trip from each part of Greater Sydney to ${b.name} (${b.address}), arriving by ${o.when}. ` +
      `Each hexagon is coloured by one sample building near its centre.`;
  return (
    <header>
      <p className="eyebrow">Greater Sydney · public transport · {night ? "earliest" : "fastest"} trip</p>
      <h1>{title}</h1>
      <p className="sub">{sub}</p>
      <div className="stats">
        <div className="stat">
          <b>{fmt(s.computed)} <span>of {fmt(n)}</span></b>
          <span>hexagons computed ({(s.pct * 100).toFixed(s.pct < 0.1 ? 1 : 0)}%)</span>
          <div className="progress" aria-hidden="true"><i style={{ width: `${(s.pct * 100).toFixed(2)}%` }} /></div>
        </div>
        <Stat value={s.median === null ? "–" : `${s.median} min`} label={night ? "median time" : "median trip"} />
        <Stat value={s.fastest === null ? "–" : `${s.fastest} min`} label="fastest" />
        {s.morning > 0 && <Stat value={fmt(s.morning)} label="only reachable next morning" />}
        <Stat value={fmt(s.tooFar)} label={`with stops over ${WALK_LIMIT} walk`} />
        <Stat value={fmt(s.noJourney)} label={night ? `with no trip within ${o.maxWaitHours} h` : "with no journey found"} />
      </div>
    </header>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return <div className="stat"><b>{value}</b><span>{label}</span></div>;
}
```

- [ ] **Step 8: Create `web/components/Controls.tsx`**

```tsx
import type { FilterName, MetricName } from "../lib/metrics";
import type { DatasetSummary } from "../lib/types";

const METRIC_BUTTONS: [MetricName, string][] = [["time", "Journey time"], ["walk", "Walking"], ["rides", "Rides"]];
// [filter, label, only for return datasets with next-morning trips]
const FILTER_CHIPS: [FilterName, string, boolean][] = [
  ["all", "All trips", false], ["train", "Using train", false], ["bus", "Bus only", false],
  ["ferry", "Using ferry", false], ["tram", "Using light rail", false],
  ["tonight", "Tonight", true], ["morning", "Next morning", true],
];

interface Props {
  datasets: DatasetSummary[]; datasetId: string; pickStatus: string; onPick: (id: string) => void;
  metric: MetricName; onMetric: (m: MetricName) => void;
  filter: FilterName; onFilter: (f: FilterName) => void;
  nightFilters: boolean; isReturn: boolean;
  hasLines: boolean; showLines: boolean; onToggleLines: () => void;
}

export default function Controls(p: Props) {
  return (
    <div className="controls">
      <div className="group picker">
        <label htmlFor="dataset">Dataset</label>
        <select id="dataset" value={p.datasetId} disabled={!p.datasets.length} onChange={(e) => p.onPick(e.target.value)}>
          {p.datasets.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
        <span className="pick-status" role="status">{p.pickStatus}</span>
      </div>
      <div className="group" role="group" aria-label="Colour by">
        <span>Colour by</span>
        <div className="seg">
          {METRIC_BUTTONS.map(([v, label]) => (
            <button key={v} type="button" aria-pressed={p.metric === v} onClick={() => p.onMetric(v)}>
              {v === "time" && p.isReturn ? "Time to get there" : label}
            </button>
          ))}
        </div>
      </div>
      <div className="group" role="group" aria-label="Show trips">
        <span>Show</span>
        <div className="group">
          {FILTER_CHIPS.map(([v, label, night]) => (
            <button key={v} type="button" className="chip" hidden={night && !p.nightFilters}
              aria-pressed={p.filter === v} onClick={() => p.onFilter(v)}>{label}</button>
          ))}
        </div>
      </div>
      {p.hasLines && (
        <div className="group" role="group" aria-label="Base map">
          <span>Base map</span>
          <button type="button" className="chip" aria-pressed={p.showLines} onClick={p.onToggleLines}>Rail &amp; ferry lines</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 9: Create `web/components/Legend.tsx`**

```tsx
import { fmt } from "../lib/format";
import { CLS, isReturn, metricOf, noTripLabel, TOO_FAR, type FilterName, type MetricName } from "../lib/metrics";
import type { Overlay } from "../lib/types";

interface Props { metricName: MetricName; filter: FilterName; counts: number[]; overlay: Overlay; n: number; }

export default function Legend({ metricName, filter, counts, overlay: o, n }: Props) {
  const M = metricOf(metricName, o);
  const bandMax = Math.max(1, ...counts.slice(CLS.ramp));
  return (
    <section className="legend" aria-labelledby="legend-title">
      <h2 id="legend-title">{M.title}</h2>
      <div className="bars">
        {M.steps.map((r, b) => <Row key={r} bg={`var(--r${r})`} label={M.labels[b]} n={counts[CLS.ramp + r]} barMax={bandMax} />)}
        {counts[CLS.morning] > 0 && <Row bg="var(--morning)" label="Only next morning" n={counts[CLS.morning]} barMax={bandMax} />}
        <span className="sep" />
        {filter === "all" ? (
          <>
            <Row bg="var(--toofar)" label={TOO_FAR} n={counts[CLS.tooFar]} />
            <Row bg="var(--nojourney)" label={isReturn(o) ? noTripLabel(o) : "No journey found"} n={counts[CLS.noJourney]} />
            {counts[CLS.notFound] > 0 && <Row hatch label="Address not in planner" n={counts[CLS.notFound]} />}
            <Row bg="var(--ghost)" label="Not computed yet" n={n - o.computed} />
          </>
        ) : (
          <Row bg="var(--ghost)" label="Other trips or not computed" n={counts[CLS.ghost]} />
        )}
      </div>
      <p className="note">
        {o.computed < n ? "Results are still being computed; grey areas fill in as the run continues." : "Bars show how many hexagons fall in each band."}
      </p>
    </section>
  );
}

// One legend row: four cells of the .bars grid; rows with barMax get a bar scaled to it
function Row({ bg, hatch, label, n, barMax }: { bg?: string; hatch?: boolean; label: string; n: number; barMax?: number }) {
  return (
    <>
      <span className={hatch ? "sw hatch" : "sw"} style={bg ? { background: bg } : undefined} />
      <span>{label}</span>
      <span>{barMax !== undefined && <i className="bar" style={{ display: "block", width: `${((n / barMax) * 100).toFixed(1)}%` }} />}</span>
      <span className="n">{fmt(n)}</span>
    </>
  );
}
```

- [ ] **Step 10: Create `web/components/MapKey.tsx`**

```tsx
import type { CSSProperties } from "react";
import { hasMorning, isReturn, metricOf, noTripLabel, type FilterName, type MetricName } from "../lib/metrics";
import type { Overlay } from "../lib/types";

interface Props { metricName: MetricName; filter: FilterName; overlay: Overlay; showLines: boolean; }

// On-map key: colour scale for the current metric, plus the other fills and base map lines
export default function MapKey({ metricName, filter, overlay: o, showLines }: Props) {
  const M = metricOf(metricName, o);
  const swatch = (bg: string) => <i className="sw" style={{ background: bg }} />;
  const line = (style: CSSProperties, dash?: string) => (
    <svg width="24" height="8" aria-hidden="true">
      <line x1="2" y1="4" x2="22" y2="4" strokeLinecap="round" style={style} strokeDasharray={dash} />
    </svg>
  );
  return (
    <div className="key" aria-hidden="true">
      <b>{M.key}</b>
      <div className="scale" style={{ gridTemplateColumns: `repeat(${M.steps.length}, minmax(${M.ticks ? 26 : 34}px, 1fr))` }}>
        {M.steps.map((r) => <i key={r} style={{ background: `var(--r${r})` }} />)}
        {M.ticks ? (  // numbers on the boundaries between bands, or a label under each band
          <div className="ticks">
            {M.ticks.map((t, b) => <span key={t} style={{ left: `${((b + 1) / M.steps.length) * 100}%` }}>{t}</span>)}
          </div>
        ) : M.short?.map((l) => <span key={l}>{l}</span>)}
      </div>
      <div className="extra">
        {hasMorning(o) && metricName === "time" && filter !== "tonight" && <span>{swatch("var(--morning)")}Next morning</span>}
        {filter === "all" ? (
          <>
            <span>{swatch("var(--toofar)")}Stop too far</span>
            <span>{swatch("var(--nojourney)")}{isReturn(o) ? noTripLabel(o) : "No journey"}</span>
          </>
        ) : <span>{swatch("var(--ghost)")}Other trips</span>}
        {showLines && (
          <>
            <span>{line({ stroke: "var(--ink)", strokeWidth: 2 })}Train / metro</span>
            <span>{line({ stroke: "var(--ink)", strokeWidth: 1.2 })}Light rail</span>
            <span>{line({ stroke: "var(--ink-2)", strokeWidth: 1.3 }, "4 3")}Ferry</span>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 11: Create `web/components/SuburbTable.tsx`**

```tsx
"use client";
import { useMemo, useState } from "react";
import { fmt } from "../lib/format";
import { defaultDir, sortRows, type SortKey, type SuburbRow } from "../lib/stats";

const COLUMNS: [SortKey, string][] = [
  ["name", "Suburb"], ["median", "Median trip"], ["fastest", "Fastest"], ["train", "Using train"], ["done", "Hexagons"],
];

interface Props { rows: SuburbRow[]; isReturn: boolean; timeBand: (minutes: number) => number; onPick: (cells: number[]) => void; }

export default function SuburbTable({ rows, isReturn, timeBand, onPick }: Props) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("median");
  const [dir, setDir] = useState<1 | -1>(1);
  const shown = useMemo(() => sortRows(rows, query, sortKey, dir), [rows, query, sortKey, dir]);
  const sortBy = (k: SortKey) => {
    if (k === sortKey) setDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(k); setDir(defaultDir(k)); }
  };
  return (
    <section className="suburbs" aria-labelledby="suburbs-title">
      <div className="head">
        <h2 id="suburbs-title">Suburbs</h2>
        <input type="search" placeholder="Find a suburb" aria-label="Find a suburb" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="tablebox">
        <table>
          <thead>
            <tr>
              {COLUMNS.map(([k, label]) => (
                <th key={k} scope="col">
                  <button type="button" aria-sort={k === sortKey ? (dir > 0 ? "ascending" : "descending") : undefined} onClick={() => sortBy(k)}>
                    {k === "median" && isReturn ? "Median time" : label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length ? shown.map((r) => (
              <tr key={r.name} tabIndex={0} onClick={() => onPick(r.cells)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(r.cells); } }}>
                <td>{r.name}</td>
                <td><span className="sw" style={{ background: `var(--r${timeBand(r.median)})` }} />{r.median} min</td>
                <td>{r.fastest} min</td>
                <td>{Math.round(r.trainShare * 100)}%</td>
                <td>{fmt(r.done)} / {fmt(r.total)}</td>
              </tr>
            )) : (
              <tr><td colSpan={5} className="empty">{rows.length ? "No suburb matches that search." : "No suburbs have results yet."}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="note">Each hexagon is about 400 m across and shows one sample building near its centre. Select a suburb to zoom to it.</p>
    </section>
  );
}
```

- [ ] **Step 12: Create `web/components/Credits.tsx`**

```tsx
export default function Credits() {
  return (
    <footer className="note credits">
      Data: <a href="https://geoscape.com.au/data/g-naf/">G-NAF</a> © Geoscape Australia,{" "}
      <a href="https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3">ABS mesh blocks</a>,
      and <a href="https://opendata.transport.nsw.gov.au/">Transport for NSW</a> timetables (CC BY 4.0);
      journeys from the <a href="https://address-info.d.imaxim.org/docs">Address Info API</a>.
    </footer>
  );
}
```

- [ ] **Step 13: Create `web/components/TravelMap.tsx`**

```tsx
"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { emptyOverlay, loadDataset, loadSite, pickInitialDataset } from "../lib/data";
import { classify, hasMorning, isReturn, metricOf, type FilterName, type MetricName } from "../lib/metrics";
import { classCounts, suburbRows } from "../lib/stats";
import { rememberDataset, rememberedDataset } from "../lib/storage";
import type { DatasetData, Overlay, SiteData } from "../lib/types";
import Controls from "./Controls";
import Credits from "./Credits";
import Header from "./Header";
import Legend from "./Legend";
import MapKey from "./MapKey";
import SuburbTable from "./SuburbTable";

// Loads site.json, the hexagons and dataset list; the page renders once it has them
export default function TravelMap() {
  const [site, setSite] = useState<SiteData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    loadSite().then(setSite, (err: Error) => setError(`Couldn't load the map data (${err.message}).`));
  }, []);
  if (site) return <Explorer site={site} />;
  return (
    <div className="wrap">
      <header>
        <p className="eyebrow">Greater Sydney · public transport · fastest trip</p>
        <h1>Sydney travel times</h1>
        <p className="sub" role="status">{error || "Loading the map…"}</p>
      </header>
      <div className="mapbox" />
    </div>
  );
}

function Explorer({ site }: { site: SiteData }) {
  const n = site.total;
  const [overlay, setOverlay] = useState<Overlay>(() => emptyOverlay(n));
  const [datasetId, setDatasetId] = useState(() => pickInitialDataset(site.datasets, rememberedDataset()) ?? "");
  const [pickStatus, setPickStatus] = useState("");
  const [metric, setMetric] = useState<MetricName>("time");
  const [filter, setFilter] = useState<FilterName>("all");
  const [showLines, setShowLines] = useState(true);
  const cache = useRef(new Map<string, DatasetData>());
  const wanted = useRef("");
  const initial = useRef(datasetId);

  // Fetch map_data/<id>.json on selection, and remember the choice per viewer
  const selectDataset = useCallback(async (id: string) => {
    wanted.current = id;
    setDatasetId(id);
    setPickStatus("Loading…");
    try {
      let data = cache.current.get(id);
      if (!data) {
        data = await loadDataset(id);
        cache.current.set(id, data);
      }
      if (wanted.current !== id) return;  // another dataset was picked meanwhile
      rememberDataset(id);
      setPickStatus("");
      setOverlay(data);
      if (!hasMorning(data)) setFilter((f) => (f === "tonight" || f === "morning" ? "all" : f));
    } catch (err) {
      if (wanted.current === id) setPickStatus(`Couldn't load this dataset (${(err as Error).message}).`);
    }
  }, []);
  useEffect(() => { if (initial.current) void selectDataset(initial.current); }, [selectDataset]);

  const cls = useMemo(() => classify(overlay, metric, filter, n), [overlay, metric, filter, n]);
  const counts = useMemo(() => classCounts(cls), [cls]);
  const rows = useMemo(() => suburbRows(site, overlay), [site, overlay]);
  const lines = showLines && !!site.transit;
  const timeBand = metricOf("time", overlay).band;

  return (
    <div className="wrap">
      <Header o={overlay} n={n} hasDatasets={site.datasets.length > 0} />
      <Controls datasets={site.datasets} datasetId={datasetId} pickStatus={pickStatus} onPick={selectDataset}
        metric={metric} onMetric={setMetric} filter={filter} onFilter={setFilter}
        nightFilters={hasMorning(overlay)} isReturn={isReturn(overlay)}
        hasLines={!!site.transit} showLines={lines} onToggleLines={() => setShowLines((s) => !s)} />
      <div className="mapbox">
        <MapKey metricName={metric} filter={filter} overlay={overlay} showLines={lines} />
      </div>
      <div className="below">
        <Legend metricName={metric} filter={filter} counts={counts} overlay={overlay} n={n} />
        <SuburbTable rows={rows} isReturn={isReturn(overlay)} timeBand={timeBand} onPick={() => {}} />
      </div>
      <Credits />
    </div>
  );
}
```

- [ ] **Step 14: Replace `web/app/page.tsx`**

```tsx
import TravelMap from "../components/TravelMap";

export default function Page() {
  return <TravelMap />;
}
```

- [ ] **Step 15: Run every test and the typecheck**

Run: `cd web && npm run typecheck && npm test && npm run test:e2e`
Expected: typecheck exits 0, unit tests PASS (36), and end-to-end tests PASS (8).

- [ ] **Step 16: Commit**

```bash
git add web
git commit -m "Port the map page's header, controls, legend, key and suburb table to React"
```

---

### Task 6: The canvas map, tooltip and suburb zoom

**Files:**
- Create: `web/lib/renderer.ts`, `web/lib/pointer.ts`, `web/components/MapCanvas.tsx`, `web/components/Tooltip.tsx`, `web/tests/e2e/map.spec.ts`
- Modify: `web/components/TravelMap.tsx` (imports, the `.mapbox` placeholder, `SuburbTable onPick`)

**Interfaces:**
- Consumes: `Geometry`, `COS` (Task 4), `CLASS_COUNT`, `isReturn`, `placeName`, `WALK_LIMIT` (Task 4), `trackHexagonClick` (Task 3), `fmt`, `km`, `mins` (Task 3), `MapKey` (Task 5)
- Produces:
  - `class MapRenderer { width; height; constructor(canvas, geometry, labels, transit); setClasses(cls); setShowLines(b); setBuilding(b); setHover(i); cellAtScreen(x, y); pan(dx, dy); zoomAt(f, x, y); zoomBy(f); fitAll(); zoomToCells(cells); destroy() }`
  - `attachPointer(canvas, map, { hover(i, x, y), hideTip(), click(i) }): { unpin(); detach() }`
  - `MapCanvas({ ref?: Ref<MapHandle>, site, geometry, cls, overlay, showLines, datasetId, mapKey })` and `interface MapHandle { zoomToCells(cells: number[]): void }`

- [ ] **Step 1: Write the failing end-to-end tests in `web/tests/e2e/map.spec.ts`**

```ts
import { expect, test, type Page } from "@playwright/test";
import { ONWARD_ID } from "../fixtures";
import { serveFixtures } from "./helpers";

// Canvas pixel at CSS coordinates relative to the canvas
async function pixel(page: Page, x: number, y: number) {
  return page.locator("canvas").evaluate((c: HTMLCanvasElement, [x, y]) => {
    const d = c.getContext("2d")!.getImageData(Math.round(x * devicePixelRatio), Math.round(y * devicePixelRatio), 1, 1).data;
    return [d[0], d[1], d[2]];
  }, [x, y]);
}
// A point inside hexagon 0, below the building marker and the rail line through its centre
async function insideFirstHexagon(page: Page) {
  const box = (await page.locator("canvas").boundingBox())!;
  return { x: box.width / 2, y: box.height / 2 + 30, pageX: box.x + box.width / 2, pageY: box.y + box.height / 2 + 30 };
}
async function open(page: Page) {
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test Building");
}

test("colours a hexagon with a 25-minute trip in the first ramp colour", async ({ page }) => {
  await open(page);
  const p = await insideFirstHexagon(page);
  await expect.poll(() => pixel(page, p.x, p.y)).toEqual([246, 211, 26]);  // --r0 in the light theme
});

test("hovering a hexagon shows its trip", async ({ page }) => {
  await open(page);
  const p = await insideFirstHexagon(page);
  await page.mouse.move(p.pageX, p.pageY);
  const tip = page.locator(".tip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("1 TEST STREET, SYDNEY");
  await expect(tip).toContainText("25 min");
  await expect(tip).toContainText("Train T1");
  await expect(tip).toContainText("Central Station → Town Hall Station");
  await page.mouse.move(1, 1);
  await expect(tip).toBeHidden();
});

test("clicking a hexagon sends a hexagon_click event to Google Analytics", async ({ page }) => {
  await open(page);
  await page.waitForFunction(() => typeof window.gtag === "function");
  const p = await insideFirstHexagon(page);
  await page.mouse.click(p.pageX, p.pageY);
  const events = await page.evaluate(() =>
    (window as unknown as { dataLayer: IArguments[] }).dataLayer.map((a) => Array.from(a)).filter((a) => a[1] === "hexagon_click"));
  expect(events).toEqual([["event", "hexagon_click", { latitude: -33.87174, longitude: 151.20669, suburb: "Sydney", dataset: ONWARD_ID }]]);
});

test("redraws in the dark palette when the colour scheme changes", async ({ page }) => {
  await open(page);
  await expect.poll(() => pixel(page, 5, 5)).toEqual([252, 252, 251]);  // --surface, light
  await page.emulateMedia({ colorScheme: "dark" });
  await expect.poll(() => pixel(page, 5, 5)).toEqual([26, 26, 25]);  // --surface, dark
});

test("labels use the Barlow web fonts", async ({ page }) => {
  await open(page);
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    const cs = getComputedStyle(document.documentElement);
    return { cond: cs.getPropertyValue("--cond"), sans: cs.getPropertyValue("--sans"),
      loaded: [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family) };
  });
  expect(fonts.cond).toContain("Barlow");
  expect(fonts.sans).toContain("Barlow");
  expect(fonts.loaded.some((f) => f.includes("Barlow"))).toBe(true);
});

test("zoom buttons and suburb rows move the map", async ({ page }) => {
  await open(page);
  const canvas = page.locator("canvas");
  await page.waitForTimeout(300);
  const before = await canvas.screenshot();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.waitForTimeout(300);
  const zoomed = await canvas.screenshot();
  expect(zoomed.equals(before)).toBe(false);
  await page.getByRole("button", { name: "Show all of Sydney" }).click();
  await page.locator(".tablebox tbody tr", { hasText: "Sydney" }).click();
  await page.waitForTimeout(300);
  expect((await canvas.screenshot()).equals(before)).toBe(false);
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web && npx playwright test tests/e2e/map.spec.ts`
Expected: FAIL. There is no `canvas` element yet.

- [ ] **Step 3: Create `web/lib/renderer.ts`**

```ts
import { COS, type Geometry } from "./geometry";
import { CLASS_COUNT } from "./metrics";
import type { Building, Label, Transit } from "./types";

interface Tokens {
  surface: string; ink: string; ink2: string; ghost: string; nojourney: string; morning: string; toofar: string;
  ramp: string[]; hatch: CanvasPattern | string; sans: string; cond: string;
}

// Draws the hexagon map: pan and zoom state, the hexagon layer, rail and ferry lines, and labels.
// Colours and fonts come from the page's CSS tokens, re-read when the colour scheme changes.
export class MapRenderer {
  width = 0;
  height = 0;
  private canvas: HTMLCanvasElement;
  private g: Geometry;
  private labels: Label[];
  private transit: Transit | null;
  private ctx: CanvasRenderingContext2D;
  private dpr = 1;
  private k = 1;  // pixels per world unit
  private tx = 0;
  private ty = 0;
  private kFit = 1;  // k when the whole map fits
  private hover = -1;
  private cls: Uint8Array;
  private showLines = true;
  private building: Building | null = null;
  private linePaths: Record<string, Path2D> = {};
  private T!: Tokens;
  private frame = 0;
  private destroyed = false;
  // Hexagons are drawn into an offscreen layer (with a margin around the view) only when the
  // view settles or the colours change. While panning, zooming or hovering, the last layer is
  // just moved and scaled, so frames cost one image copy instead of 32k polygons.
  private layer = document.createElement("canvas");
  private lctx: CanvasRenderingContext2D;
  private lk = 0;
  private ltx = 0;
  private lty = 0;
  private margin = 0;
  private dirty = true;
  private moving = false;
  private settle: ReturnType<typeof setTimeout> | undefined;
  private resizeObserver: ResizeObserver;
  private themeObserver: MutationObserver;
  private darkQuery = matchMedia("(prefers-color-scheme: dark)");
  private retheme = () => { this.readTokens(); this.invalidate(); };

  constructor(canvas: HTMLCanvasElement, geometry: Geometry, labels: Label[], transit: Transit | null) {
    this.canvas = canvas;
    this.g = geometry;
    this.labels = labels;
    this.transit = transit;
    this.ctx = canvas.getContext("2d")!;
    this.lctx = this.layer.getContext("2d")!;
    this.cls = new Uint8Array(geometry.n);
    // rail, light rail and ferry lines as world-space paths, built once
    if (transit) for (const [layer, lines] of Object.entries(transit.lines)) {
      const p = new Path2D();
      for (const l of lines) for (let j = 0; j < l.length; j += 2) {
        const x = l[j] * COS, y = -l[j + 1];
        if (j) p.lineTo(x, y); else p.moveTo(x, y);
      }
      this.linePaths[layer] = p;
    }
    this.readTokens();
    this.darkQuery.addEventListener("change", this.retheme);
    this.themeObserver = new MutationObserver(this.retheme);
    this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    document.fonts?.ready.then(() => this.schedule());
  }

  destroy() {
    this.destroyed = true;
    this.resizeObserver.disconnect();
    this.themeObserver.disconnect();
    this.darkQuery.removeEventListener("change", this.retheme);
    cancelAnimationFrame(this.frame);
    clearTimeout(this.settle);
  }

  setClasses(cls: Uint8Array) { this.cls = cls; this.invalidate(); }
  setShowLines(show: boolean) { this.showLines = show && !!this.transit; this.invalidate(); }
  setBuilding(building: Building | null) { this.building = building; this.schedule(); }
  setHover(i: number) { if (i !== this.hover) { this.hover = i; this.schedule(); } }
  cellAtScreen(sx: number, sy: number) { return this.g.cellAt((sx - this.tx) / this.k, (sy - this.ty) / this.k); }

  pan(dx: number, dy: number) { this.tx += dx; this.ty += dy; this.interact(); this.schedule(); }
  zoomAt(f: number, sx: number, sy: number) {
    const nk = Math.min(Math.max(this.k * f, this.kFit * 0.7), this.kFit * 80);
    this.tx = sx - ((sx - this.tx) * nk) / this.k;
    this.ty = sy - ((sy - this.ty) * nk) / this.k;
    this.k = nk;
    this.interact(); this.schedule();
  }
  zoomBy(f: number) { this.zoomAt(f, this.width / 2, this.height / 2); }
  fitAll() {
    const { minX, minY, maxX, maxY, R } = this.g;
    this.fit(minX - R, minY - R, maxX + R, maxY + R);
    this.kFit = this.k;
    this.schedule();
  }
  zoomToCells(cells: number[]) {
    const { cx, cy, R } = this.g;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const i of cells) { x0 = Math.min(x0, cx[i]); x1 = Math.max(x1, cx[i]); y0 = Math.min(y0, cy[i]); y1 = Math.max(y1, cy[i]); }
    this.fit(x0 - R * 3, y0 - R * 3, x1 + R * 3, y1 + R * 3, 0.8);
    this.k = Math.min(this.k, this.kFit * 80);
    this.schedule();
  }

  private fit(x0: number, y0: number, x1: number, y1: number, pad = 0.92) {
    const { R } = this.g;
    const bw = Math.max(x1 - x0, R * 12), bh = Math.max(y1 - y0, R * 12);
    this.k = Math.min(this.width / bw, this.height / bh) * pad;
    this.tx = this.width / 2 - ((x0 + x1) / 2) * this.k;
    this.ty = this.height / 2 - ((y0 + y1) / 2) * this.k;
  }

  private resize() {
    const r = this.canvas.getBoundingClientRect();
    const first = this.width === 0, ox = this.width / 2, oy = this.height / 2;
    this.width = r.width; this.height = r.height; this.dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    if (first) this.fitAll();
    else { this.tx += this.width / 2 - ox; this.ty += this.height / 2 - oy; }
    this.invalidate();
  }

  private readTokens() {
    const cs = getComputedStyle(document.documentElement);
    const g = (name: string) => cs.getPropertyValue(name).trim();
    const T: Tokens = {
      surface: g("--surface"), ink: g("--ink"), ink2: g("--ink-2"), ghost: g("--ghost"), nojourney: g("--nojourney"),
      morning: g("--morning"), toofar: g("--toofar"), ramp: Array.from({ length: 10 }, (_, k) => g(`--r${k}`)),
      hatch: g("--nojourney"), sans: g("--sans"), cond: g("--cond"),
    };
    const c = document.createElement("canvas");
    c.width = c.height = 6;
    const x = c.getContext("2d")!;
    x.fillStyle = T.ghost; x.fillRect(0, 0, 6, 6);
    x.strokeStyle = T.nojourney; x.lineWidth = 1.6;
    x.beginPath(); x.moveTo(-1, 7); x.lineTo(7, -1); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(5, 7); x.lineTo(7, 5); x.stroke();
    T.hatch = this.ctx.createPattern(c, "repeat") ?? T.nojourney;
    this.T = T;
  }

  private schedule() {
    if (this.frame || this.destroyed) return;
    this.frame = requestAnimationFrame(() => { this.frame = 0; this.draw(); });
  }
  private invalidate() { this.dirty = true; this.schedule(); }
  private interact() {
    this.moving = true;
    clearTimeout(this.settle);
    this.settle = setTimeout(() => { this.moving = false; this.schedule(); }, 150);
  }

  private renderLayer() {
    const { n, cx, cy, start, P, R } = this.g, { k, dpr, lctx, T } = this;
    const MG = (this.margin = Math.round(Math.max(this.width, this.height) * 0.25));
    const LW = this.width + 2 * MG, LH = this.height + 2 * MG, ox = this.tx + MG, oy = this.ty + MG;
    if (this.layer.width !== Math.round(LW * dpr) || this.layer.height !== Math.round(LH * dpr)) {
      this.layer.width = Math.round(LW * dpr); this.layer.height = Math.round(LH * dpr);
    }
    lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lctx.fillStyle = T.surface; lctx.fillRect(0, 0, LW, LH);
    const paths = Array.from({ length: CLASS_COUNT }, () => new Path2D());
    const m = R * k;
    for (let i = 0; i < n; i++) {
      const sx = cx[i] * k + ox, sy = cy[i] * k + oy;
      if (sx < -m || sy < -m || sx > LW + m || sy > LH + m) continue;
      const p = paths[this.cls[i]];
      for (let j = start[i]; j < start[i + 1]; j++) {
        const x = P[2 * j] * k + ox, y = P[2 * j + 1] * k + oy;
        if (j === start[i]) p.moveTo(x, y); else p.lineTo(x, y);
      }
      p.closePath();
    }
    const fills = [T.ghost, T.nojourney, T.hatch, ...T.ramp, T.morning, T.toofar];
    paths.forEach((p, c) => { lctx.fillStyle = fills[c]; lctx.fill(p); });
    if (m > 7) {  // surface gap between hexagons once they are big enough to see
      lctx.strokeStyle = T.surface; lctx.lineWidth = Math.min(2, m / 10);
      paths.forEach((p) => lctx.stroke(p));
    }
    if (this.showLines) this.drawLines(ox, oy);
    this.lk = k; this.ltx = this.tx; this.lty = this.ty; this.dirty = false;
  }

  private drawLines(ox: number, oy: number) {
    // paths are in world units, so draw them through the view transform and scale widths back to pixels
    const { lctx, k, dpr, T, linePaths } = this;
    lctx.save();
    lctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * ox, dpr * oy);
    lctx.lineJoin = lctx.lineCap = "round";
    const z = Math.min(1.5, Math.max(0.7, Math.sqrt(k / this.kFit) * 0.55));  // thinner when zoomed out
    const stroke = (p: Path2D | undefined, width: number, color: string, dash?: number[]) => {
      if (!p) return;
      lctx.lineWidth = (width * z) / k; lctx.strokeStyle = color;
      lctx.setLineDash(dash ? dash.map((d) => (d * z) / k) : []); lctx.stroke(p);
    };
    stroke(linePaths.ferry, 1.3, T.ink2, [4, 3]);
    stroke(linePaths.light_rail, 3.2, T.surface); stroke(linePaths.light_rail, 1.2, T.ink);
    stroke(linePaths.rail, 4, T.surface); stroke(linePaths.rail, 1.8, T.ink);
    lctx.restore();
  }

  private draw() {
    const { ctx, dpr, T } = this;
    if (!this.width || !this.height) return;  // not laid out yet
    if (this.dirty || (!this.moving && (this.lk !== this.k || this.ltx !== this.tx || this.lty !== this.ty))) this.renderLayer();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = T.surface; ctx.fillRect(0, 0, this.width, this.height);
    // layer point p (CSS px, minus margin) is world (p - ltx) / lk; on screen it is at s * p + tx - ltx * s
    const s = this.k / this.lk;
    ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * (this.tx - this.ltx * s), dpr * (this.ty - this.lty * s));
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.layer, -this.margin, -this.margin, this.layer.width / dpr, this.layer.height / dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const h = this.hover, { start, P } = this.g;
    if (h >= 0) {
      ctx.beginPath();
      for (let j = start[h]; j < start[h + 1]; j++) {
        const x = P[2 * j] * this.k + this.tx, y = P[2 * j + 1] * this.k + this.ty;
        if (j === start[h]) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.lineWidth = 2.5; ctx.strokeStyle = T.surface; ctx.stroke();
      ctx.lineWidth = 1.5; ctx.strokeStyle = T.ink; ctx.stroke();
    }
    this.drawLabels();
  }

  private drawLabels() {
    const { ctx, k, tx, ty, T, width: W, height: H } = this;
    const boxes: number[][] = [];
    const put = (text: string, x: number, y: number, font: string, color: string, weight = 2) => {
      ctx.font = font;
      const w = ctx.measureText(text).width;
      const b = [x - w / 2 - 3, y - 9, x + w / 2 + 3, y + 9];
      if (b[2] < 0 || b[0] > W || b[3] < 0 || b[1] > H) return;
      if (boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) return;
      boxes.push(b);
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      ctx.lineWidth = weight * 2; ctx.strokeStyle = T.surface; ctx.strokeText(text, x, y);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
    };
    const zoom = k / this.kFit, stations: [string, number, number][] = [];
    if (this.showLines && this.transit && zoom > 3) {
      for (const [name, lx, ly, layer] of this.transit.stations) {
        if (layer !== "rail" && zoom < 6) continue;
        const x = lx * COS * k + tx, y = -ly * k + ty;
        if (x < -10 || y < -10 || x > W + 10 || y > H + 10) continue;
        ctx.beginPath(); ctx.arc(x, y, layer === "rail" ? 3.5 : 2.6, 0, Math.PI * 2);
        ctx.fillStyle = T.surface; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = T.ink; ctx.stroke();
        stations.push([name.replace(/ (Station|Wharf|Light Rail)$/, ""), x, y]);
      }
    }
    // the dataset's building first, so labels avoid it
    if (this.building) {
      const qx = this.building.xy[0] * COS * k + tx, qy = -this.building.xy[1] * k + ty;
      ctx.beginPath(); ctx.arc(qx, qy, 6, 0, Math.PI * 2);
      ctx.fillStyle = T.ink; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = T.surface; ctx.stroke();
      boxes.push([qx - 8, qy - 8, qx + 8, qy + 8]);
      put(this.building.name, qx, qy - 17, `700 14px ${T.cond}`, T.ink, 3);
    }
    const showTier2 = zoom > 2.2;
    for (const [name, lx, ly, tier] of this.labels) {
      if (tier === 2 && !showTier2) continue;
      put(name, lx * COS * k + tx, -ly * k + ty, `${tier === 1 ? "600 13px" : "500 12px"} ${T.cond}`, T.ink, 2);
    }
    if (zoom > 9) for (const [name, x, y] of stations) put(name, x, y - 12, `500 11px ${T.sans}`, T.ink2, 2);
  }
}
```

- [ ] **Step 4: Create `web/lib/pointer.ts`**

```ts
import type { MapRenderer } from "./renderer";

export interface PointerCallbacks {
  hover(i: number, x: number, y: number): void;  // hexagon under the pointer, or -1
  hideTip(): void;
  click(i: number): void;  // a hexagon was clicked or tapped
}
export interface PointerControl { unpin(): void; detach(): void; }

// Drag to pan, pinch or wheel to zoom, hover or tap to inspect. A tap on a touch screen pins
// the tooltip until the next gesture, since there is no hover to keep it open.
export function attachPointer(canvas: HTMLCanvasElement, map: MapRenderer, on: PointerCallbacks): PointerControl {
  const ptrs = new Map<number, [number, number]>();
  let moved = 0, lastPinch = 0, pinned = false;
  const local = (e: MouseEvent): [number, number] => {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  const down = (e: PointerEvent) => {
    canvas.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, local(e)); moved = 0;
    if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; lastPinch = Math.hypot(a[0] - b[0], a[1] - b[1]); }
  };
  const move = (e: PointerEvent) => {
    const [x, y] = local(e);
    const last = ptrs.get(e.pointerId);
    if (!last) {
      if (e.pointerType === "mouse" && !pinned) on.hover(map.cellAtScreen(x, y), x, y);
      return;
    }
    ptrs.set(e.pointerId, [x, y]);
    if (ptrs.size === 1) {
      map.pan(x - last[0], y - last[1]);
      moved += Math.abs(x - last[0]) + Math.abs(y - last[1]);
      if (moved > 4) { canvas.classList.add("dragging"); on.hideTip(); pinned = false; }
    } else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (lastPinch) map.zoomAt(d / lastPinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      lastPinch = d; moved = 99;
    }
  };
  const release = (e: PointerEvent) => {
    const wasTap = ptrs.size === 1 && moved <= 4;
    ptrs.delete(e.pointerId); canvas.classList.remove("dragging");
    if (ptrs.size < 2) lastPinch = 0;
    if (wasTap && e.type === "pointerup") {
      const [x, y] = local(e);
      const i = map.cellAtScreen(x, y);
      pinned = e.pointerType !== "mouse" && i >= 0;
      on.hover(i, x, y);
      if (i >= 0) on.click(i);
    }
  };
  const leave = (e: PointerEvent) => { if (e.pointerType === "mouse" && !pinned) on.hover(-1, 0, 0); };
  const wheel = (e: WheelEvent) => {
    e.preventDefault();
    const [x, y] = local(e);
    map.zoomAt(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0018)), x, y);
    on.hideTip(); pinned = false;
  };

  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", leave);
  canvas.addEventListener("wheel", wheel, { passive: false });
  return {
    unpin: () => { pinned = false; },
    detach: () => {
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", release);
      canvas.removeEventListener("pointercancel", release);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("wheel", wheel);
    },
  };
}
```

- [ ] **Step 5: Create `web/components/Tooltip.tsx`**

```tsx
"use client";
import { useLayoutEffect, useRef } from "react";
import { fmt, km, mins } from "../lib/format";
import { isReturn, placeName, WALK_LIMIT } from "../lib/metrics";
import type { Overlay, SiteData } from "../lib/types";

const MODE_NAMES: [number, string][] = [[1, "Bus"], [2, "Train / Metro"], [4, "Ferry"], [8, "Light rail"]];
const LEG_NAMES: Record<string, string> = {
  walk: "Walk", bus: "Bus", coach: "Coach", train: "Train", metro: "Metro", light_rail: "Light rail", ferry: "Ferry",
};

interface Props { site: SiteData; o: Overlay; i: number; x: number; y: number; width: number; height: number; }

// Tooltip for hexagon i, placed beside the pointer at (x, y) and kept inside the map
export default function Tooltip({ site, o, i, x, y, width, height }: Props) {
  const el = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const tip = el.current!;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = x + 14, top = y + 14;
    if (left + tw > width - 8) left = x - tw - 14;
    if (top + th > height - 8) top = y - th - 14;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  });
  return <div className="tip" ref={el}><Body site={site} o={o} i={i} /></div>;
}

function Body({ site, o, i }: { site: SiteData; o: Overlay; i: number }) {
  const s = o.status[i], suburb = site.localities[site.loc[i]], night = isReturn(o);
  const time = o.when.split(" on ")[0];
  if (!s) return <><strong>{suburb}</strong><span className="muted">Not computed yet.</span></>;
  const head = <><strong>{o.address[i]}</strong><span className="muted">{suburb}</span></>;
  if (s === 2) return <>{head}<span className="muted">{night
    ? `No public transport departure from ${placeName(o)} within ${o.maxWaitHours} hours of ${time}.`
    : `No public transport journey found arriving by ${time}.`}</span></>;
  if (s === 3) return <>{head}<span className="muted">The journey planner doesn&apos;t know this address or the nearby ones tried.</span></>;
  if (s === 4) return <>{head}<span className="muted">Every trip found needs a walk of more than {WALK_LIMIT} to or from a stop.</span></>;
  const modes = MODE_NAMES.filter(([bit]) => o.modes[i] & bit);
  return (
    <>
      {head}
      {night && o.morning?.[i] ? <span className="muted">No service overnight: the first trip leaves in the morning.</span> : null}
      <div className="big">{mins(o.minutes[i] ?? 0)}</div>
      <dl>
        <dt>Leave</dt><dd>{o.depart[i]} → arrive {o.arrive[i]}</dd>
        {night && (
          <>
            <dt>Wait</dt><dd>{mins(o.wait?.[i] ?? 0)} at {placeName(o)}</dd>
            <dt>Trip</dt><dd>{mins(o.trip?.[i] ?? 0)}</dd>
          </>
        )}
        <dt>Walking</dt><dd>{o.walkMin[i]} min · {fmt(o.walkM[i] ?? 0)} m</dd>
        <dt>Rides</dt><dd>{o.transports[i]}</dd>
      </dl>
      {modes.length > 0 && <div className="modes">{modes.map(([, name]) => <b key={name}>{name}</b>)}</div>}
      <Legs o={o} i={i} />
    </>
  );
}

// One line per leg: mode, route, minutes, distance, then the stops it runs between
function Legs({ o, i }: { o: Overlay; i: number }) {
  const legs = o.legs[i];
  if (!legs) return null;
  return (
    <ol className="legs">
      {legs.map(([m, route, minutes, metres, from, to], j) => {
        const mode = o.legModes[m];
        return (
          <li key={j}>
            <b>{LEG_NAMES[mode] ?? mode}{route ? ` ${route}` : ""}</b> · {minutes} min · {km(metres)}
            {mode !== "walk" && <span className="muted">{o.stops[from]} → {o.stops[to]}</span>}
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 6: Create `web/components/MapCanvas.tsx`**

```tsx
"use client";
import { useEffect, useImperativeHandle, useRef, useState, type ReactNode, type Ref } from "react";
import { trackHexagonClick } from "../lib/analytics";
import type { Geometry } from "../lib/geometry";
import { isReturn, placeName } from "../lib/metrics";
import { attachPointer, type PointerControl } from "../lib/pointer";
import { MapRenderer } from "../lib/renderer";
import type { Overlay, SiteData } from "../lib/types";
import Tooltip from "./Tooltip";

export interface MapHandle { zoomToCells(cells: number[]): void; }

interface Props {
  ref?: Ref<MapHandle>;
  site: SiteData; geometry: Geometry; cls: Uint8Array; overlay: Overlay;
  showLines: boolean; datasetId: string; mapKey: ReactNode;
}

export default function MapCanvas({ ref, site, geometry, cls, overlay, showLines, datasetId, mapKey }: Props) {
  const box = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<MapRenderer | null>(null), pointer = useRef<PointerControl | null>(null);
  const dataset = useRef(datasetId);
  const [tip, setTip] = useState<{ i: number; x: number; y: number } | null>(null);
  const reset = () => { setTip(null); renderer.current?.setHover(-1); pointer.current?.unpin(); };

  useEffect(() => { dataset.current = datasetId; }, [datasetId]);
  useEffect(() => {
    const r = new MapRenderer(canvas.current!, geometry, site.labels, site.transit);
    renderer.current = r;
    pointer.current = attachPointer(canvas.current!, r, {
      hover: (i, x, y) => { r.setHover(i); setTip(i >= 0 ? { i, x, y } : null); },
      hideTip: () => setTip(null),
      click: (i) => trackHexagonClick(site, i, dataset.current),
    });
    return () => { pointer.current?.detach(); r.destroy(); renderer.current = null; };
  }, [geometry, site]);
  useEffect(() => { renderer.current?.setClasses(cls); }, [cls]);
  useEffect(() => { renderer.current?.setShowLines(showLines); }, [showLines]);
  useEffect(() => { renderer.current?.setBuilding(overlay.building); reset(); }, [overlay]);

  useImperativeHandle(ref, () => ({
    zoomToCells(cells: number[]) {
      renderer.current?.zoomToCells(cells);
      reset();
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      box.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    },
  }), []);

  return (
    <div className="mapbox" ref={box}>
      <canvas ref={canvas} role="img"
        aria-label={`Map of Greater Sydney coloured by travel time ${isReturn(overlay) ? "from" : "to"} ${placeName(overlay)}`} />
      <div className="hint">Drag to pan · scroll to zoom · hover a hexagon</div>
      <div className="zoom">
        <button type="button" aria-label="Zoom in" onClick={() => renderer.current?.zoomBy(1.6)}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => renderer.current?.zoomBy(1 / 1.6)}>−</button>
        <button type="button" className="reset" aria-label="Show all of Sydney" onClick={() => { renderer.current?.fitAll(); reset(); }}>All</button>
      </div>
      {mapKey}
      {tip && <Tooltip site={site} o={overlay} {...tip} width={renderer.current?.width ?? 0} height={renderer.current?.height ?? 0} />}
    </div>
  );
}
```

- [ ] **Step 7: Wire the canvas into `web/components/TravelMap.tsx`**

Add these imports:

```tsx
import { buildGeometry } from "../lib/geometry";
import MapCanvas, { type MapHandle } from "./MapCanvas";
```

In `Explorer`, after `const initial = useRef(datasetId);`, add:

```tsx
  const map = useRef<MapHandle>(null);
  const geometry = useMemo(() => buildGeometry(site), [site]);
  const zoomToSuburb = useCallback((cells: number[]) => map.current?.zoomToCells(cells), []);
```

Replace:

```tsx
      <div className="mapbox">
        <MapKey metricName={metric} filter={filter} overlay={overlay} showLines={lines} />
      </div>
```

with:

```tsx
      <MapCanvas ref={map} site={site} geometry={geometry} cls={cls} overlay={overlay} showLines={lines} datasetId={datasetId}
        mapKey={<MapKey metricName={metric} filter={filter} overlay={overlay} showLines={lines} />} />
```

Then replace `onPick={() => {}}` with `onPick={zoomToSuburb}`.

- [ ] **Step 8: Run every test and the typecheck**

Run: `cd web && npm run typecheck && npm test && npm run test:e2e`
Expected: typecheck exits 0, unit tests PASS (36), and end-to-end tests PASS (14).

- [ ] **Step 9: Commit**

```bash
git add web
git commit -m "Port the canvas map, tooltip and suburb zoom to TypeScript"
```

---

### Task 7: Publish to `docs/`, update previews, and check parity with the live site

**Files:**
- Create: `web/scripts/publish.mjs`
- Modify: `.claude/launch.json`, `README.md`
- Delete: `map_template.html`
- Regenerate: `docs/` (published build)

**Interfaces:**
- Consumes: `web/out/` from `next build` (Tasks 1-6), and `web/public/site.json` plus `map_data/` (Task 2)
- Produces: `npm run publish-site`, which builds the export and replaces `docs/` with it, including `.nojekyll`

- [ ] **Step 1: Create `web/scripts/publish.mjs`**

```js
// Replaces ../docs (served by GitHub Pages) with the static export in out/.
// Refuses to publish a build without its data, so the live site never loses its datasets.
import { cpSync, existsSync, rmSync, writeFileSync } from "node:fs";

const out = new URL("../out/", import.meta.url), docs = new URL("../../docs/", import.meta.url);
for (const path of ["index.html", "site.json", "map_data"]) {
  if (!existsSync(new URL(path, out))) {
    console.error(`out/${path} is missing: run \`uv run build_travel_time_map.py\` in the repository root, then this again.`);
    process.exit(1);
  }
}
rmSync(docs, { recursive: true, force: true });
cpSync(out, docs, { recursive: true });
writeFileSync(new URL(".nojekyll", docs), "");  // GitHub Pages' Jekyll would otherwise drop the _next folder
console.log("Published web/out to docs/");
```

- [ ] **Step 2: Check that the publish script refuses a build without data**

Run: `cd web && mv public/site.json site.json.bak; npm run publish-site; echo "exit $?"; mv site.json.bak public/site.json; git status --short ../docs`
Expected: the output includes `out/site.json is missing` and `exit 1`, and `git status` shows no changes under `docs/`.

- [ ] **Step 3: Publish the real build**

Run: `cd .. && uv run build_travel_time_map.py && cd web && npm run publish-site && ls -a ../docs ../docs/map_data`
Expected: the output includes `Published web/out to docs/`. `docs/` contains `.nojekyll`, `index.html`, `404.html`, `_next`, `site.json` and `map_data`, and `docs/map_data` holds both dataset files.

- [ ] **Step 4: Point the preview configurations at the new build.** Replace `.claude/launch.json` with:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "map-preview",
      "runtimeExecutable": "sh",
      "runtimeArgs": ["-c", "exec node web/scripts/serve.mjs docs ${PORT:-8765}"],
      "port": 8765
    },
    {
      "name": "web-dev",
      "runtimeExecutable": "sh",
      "runtimeArgs": ["-c", "cd web && exec npx next dev --port ${PORT:-3000}"],
      "port": 3000
    }
  ]
}
```

- [ ] **Step 5: Check parity against the live site.** Start `map-preview` with the preview tools and open `http://localhost:8765/sydney-travel-time/`. Side by side with https://maxim75.github.io/sydney-travel-time/, check each of these and note any difference:
  - Both datasets: title, subtitle, stats, legend counts and suburb table match.
  - The map looks the same at the default view and zoomed into the CBD (stations and tier 2 labels appear). Labels render in Barlow Condensed.
  - Hover tooltips match for an ok hexagon, a no-journey hexagon, and a next-morning hexagon (in the return dataset).
  - Light and dark themes (`resize_window` with `colorScheme`) and a 375 px wide viewport.
  - The console has no errors and every network request is 2xx (`read_network_requests`).

  Fix any difference in the owning component before continuing.

- [ ] **Step 6: Remove the old template and document the workflow.** Delete `map_template.html`. Replace the empty `README.md` with:

````markdown
# Sydney travel times

Public transport travel times across Greater Sydney, shown as a hexagon map at
https://maxim75.github.io/sydney-travel-time/.

- Python (`uv`) collects journeys and builds the map data: `uv run build_travel_time_map.py`
  writes `web/public/site.json` and `web/public/map_data/`.
- `web/` is a Next.js + TypeScript app exported as a static site. To publish:

```bash
cd web && npm install && npm run publish-site
```

  This replaces `docs/`, which GitHub Pages serves from the `main` branch. Commit `docs/` to publish.
- Develop with `npm run dev` in `web/`, then open http://localhost:3000/sydney-travel-time/. Tests: `npm test`, `npm run test:e2e`.
````

- [ ] **Step 7: Final full check**

Run: `cd web && npm run typecheck && npm test && npm run test:e2e && git -C .. status --short`
Expected: everything passes. Status shows `docs/` regenerated, `map_template.html` deleted, and `README.md` and `.claude/launch.json` modified.

- [ ] **Step 8: Commit** (pushing to `main` publishes the site, so leave that to the user)

```bash
git add -A docs map_template.html README.md .claude/launch.json web/scripts/publish.mjs
git commit -m "Publish the Next.js map to docs/ and retire the HTML template"
```
