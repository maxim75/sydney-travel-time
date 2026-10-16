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
