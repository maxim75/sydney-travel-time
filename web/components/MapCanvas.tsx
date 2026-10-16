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
