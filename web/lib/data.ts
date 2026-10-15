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
