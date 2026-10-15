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
