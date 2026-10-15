import { fmt } from "../lib/format";
import { isReturn, WALK_LIMIT } from "../lib/metrics";
import { headerStats } from "../lib/stats";
import type { Overlay } from "../lib/types";

export default function Header({ o, n, hasDatasets }: { o: Overlay; n: number; hasDatasets: boolean }) {
  const night = isReturn(o), b = o.building, s = headerStats(o, n);
  const title = !b ? "Sydney travel times"
    : night ? `How long does it take to get home from ${b.name}?` : `How long does it take to get to ${b.name}?`;
  const sub = !b
    ? (hasDatasets ? "Loading the dataset…" : "No datasets have been built yet.")
    : night
    ? `Earliest public transport trip from ${b.name} (${b.address}) to each part of Greater Sydney, leaving at ${o.when}. ` +
      `Times include waiting there for the first service, up to ${o.maxWaitHours} hours; places with no departure in that time count as no trip.`
    : `Fastest public transport trip from each part of Greater Sydney to ${b.name} (${b.address}), arriving by ${o.when}. ` +
      `Each hexagon is coloured by one sample building near its centre.`;
  return (
    <header>
      <p className="eyebrow">Greater Sydney · public transport · {night ? "earliest" : "fastest"} trip</p>
      <h1>{title}</h1>
      <p className="sub">{sub}</p>
      <div className="stats">
        <div className="stat">
          <b>{fmt(s.computed)} <span>of {fmt(n)}</span></b>
          <span>hexagons computed ({(s.pct * 100).toFixed(s.pct < 0.1 ? 1 : 0)}%)</span>
          <div className="progress" aria-hidden="true"><i style={{ width: `${(s.pct * 100).toFixed(2)}%` }} /></div>
        </div>
        <Stat value={s.median === null ? "–" : `${s.median} min`} label={night ? "median time" : "median trip"} />
        <Stat value={s.fastest === null ? "–" : `${s.fastest} min`} label="fastest" />
        {s.morning > 0 && <Stat value={fmt(s.morning)} label="only reachable next morning" />}
        <Stat value={fmt(s.tooFar)} label={`with stops over ${WALK_LIMIT} walk`} />
        <Stat value={fmt(s.noJourney)} label={night ? `with no trip within ${o.maxWaitHours} h` : "with no journey found"} />
      </div>
    </header>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return <div className="stat"><b>{value}</b><span>{label}</span></div>;
}
