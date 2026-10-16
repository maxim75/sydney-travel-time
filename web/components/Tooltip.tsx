"use client";
import { useLayoutEffect, useRef } from "react";
import { fmt, km, mins } from "../lib/format";
import { isReturn, placeName, WALK_LIMIT } from "../lib/metrics";
import type { Overlay, SiteData } from "../lib/types";

const MODE_NAMES: [number, string][] = [[1, "Bus"], [2, "Train / Metro"], [4, "Ferry"], [8, "Light rail"]];
const LEG_NAMES: Record<string, string> = {
  walk: "Walk", bus: "Bus", coach: "Coach", train: "Train", metro: "Metro", light_rail: "Light rail", ferry: "Ferry",
};

interface Props { site: SiteData; o: Overlay; i: number; x: number; y: number; width: number; height: number; }

// Tooltip for hexagon i, placed beside the pointer at (x, y) and kept inside the map
export default function Tooltip({ site, o, i, x, y, width, height }: Props) {
  const el = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const tip = el.current!;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = x + 14, top = y + 14;
    if (left + tw > width - 8) left = x - tw - 14;
    if (top + th > height - 8) top = y - th - 14;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  });
  return <div className="tip" ref={el}><Body site={site} o={o} i={i} /></div>;
}

function Body({ site, o, i }: { site: SiteData; o: Overlay; i: number }) {
  const s = o.status[i], suburb = site.localities[site.loc[i]], night = isReturn(o);
  const time = o.when.split(" on ")[0];
  if (!s) return <><strong>{suburb}</strong><span className="muted">Not computed yet.</span></>;
  const head = <><strong>{o.address[i]}</strong><span className="muted">{suburb}</span></>;
  if (s === 2) return <>{head}<span className="muted">{night
    ? `No public transport departure from ${placeName(o)} within ${o.maxWaitHours} hours of ${time}.`
    : `No public transport journey found arriving by ${time}.`}</span></>;
  if (s === 3) return <>{head}<span className="muted">The journey planner doesn&apos;t know this address or the nearby ones tried.</span></>;
  if (s === 4) return <>{head}<span className="muted">Every trip found needs a walk of more than {WALK_LIMIT} to or from a stop.</span></>;
  const modes = MODE_NAMES.filter(([bit]) => o.modes[i] & bit);
  return (
    <>
      {head}
      {night && o.morning?.[i] ? <span className="muted">No service overnight: the first trip leaves in the morning.</span> : null}
      <div className="big">{mins(o.minutes[i] ?? 0)}</div>
      <dl>
        <dt>Leave</dt><dd>{o.depart[i]} → arrive {o.arrive[i]}</dd>
        {night && (
          <>
            <dt>Wait</dt><dd>{mins(o.wait?.[i] ?? 0)} at {placeName(o)}</dd>
            <dt>Trip</dt><dd>{mins(o.trip?.[i] ?? 0)}</dd>
          </>
        )}
        <dt>Walking</dt><dd>{o.walkMin[i]} min · {fmt(o.walkM[i] ?? 0)} m</dd>
        <dt>Rides</dt><dd>{o.transports[i]}</dd>
      </dl>
      {modes.length > 0 && <div className="modes">{modes.map(([, name]) => <b key={name}>{name}</b>)}</div>}
      <Legs o={o} i={i} />
    </>
  );
}

// One line per leg: mode, route, minutes, distance, then the stops it runs between
function Legs({ o, i }: { o: Overlay; i: number }) {
  const legs = o.legs[i];
  if (!legs) return null;
  return (
    <ol className="legs">
      {legs.map(([m, route, minutes, metres, from, to], j) => {
        const mode = o.legModes[m];
        return (
          <li key={j}>
            <b>{LEG_NAMES[mode] ?? mode}{route ? ` ${route}` : ""}</b> · {minutes} min · {km(metres)}
            {mode !== "walk" && <span className="muted">{o.stops[from]} → {o.stops[to]}</span>}
          </li>
        );
      })}
    </ol>
  );
}
