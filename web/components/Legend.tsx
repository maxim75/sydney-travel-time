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
