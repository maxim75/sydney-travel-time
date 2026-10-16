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
