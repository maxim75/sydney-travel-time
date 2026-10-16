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
