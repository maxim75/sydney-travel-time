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
