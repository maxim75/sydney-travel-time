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
