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
