"use client";
import { useMemo, useState } from "react";
import { fmt } from "../lib/format";
import { defaultDir, sortRows, type SortKey, type SuburbRow } from "../lib/stats";

const COLUMNS: [SortKey, string][] = [
  ["name", "Suburb"], ["median", "Median trip"], ["fastest", "Fastest"], ["train", "Using train"], ["done", "Hexagons"],
];

interface Props { rows: SuburbRow[]; isReturn: boolean; timeBand: (minutes: number) => number; onPick: (cells: number[]) => void; }

export default function SuburbTable({ rows, isReturn, timeBand, onPick }: Props) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("median");
  const [dir, setDir] = useState<1 | -1>(1);
  const shown = useMemo(() => sortRows(rows, query, sortKey, dir), [rows, query, sortKey, dir]);
  const sortBy = (k: SortKey) => {
    if (k === sortKey) setDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(k); setDir(defaultDir(k)); }
  };
  return (
    <section className="suburbs" aria-labelledby="suburbs-title">
      <div className="head">
        <h2 id="suburbs-title">Suburbs</h2>
        <input type="search" placeholder="Find a suburb" aria-label="Find a suburb" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="tablebox">
        <table>
          <thead>
            <tr>
              {COLUMNS.map(([k, label]) => (
                <th key={k} scope="col">
                  <button type="button" aria-sort={k === sortKey ? (dir > 0 ? "ascending" : "descending") : undefined} onClick={() => sortBy(k)}>
                    {k === "median" && isReturn ? "Median time" : label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length ? shown.map((r) => (
              <tr key={r.name} tabIndex={0} onClick={() => onPick(r.cells)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(r.cells); } }}>
                <td>{r.name}</td>
                <td><span className="sw" style={{ background: `var(--r${timeBand(r.median)})` }} />{r.median} min</td>
                <td>{r.fastest} min</td>
                <td>{Math.round(r.trainShare * 100)}%</td>
                <td>{fmt(r.done)} / {fmt(r.total)}</td>
              </tr>
            )) : (
              <tr><td colSpan={5} className="empty">{rows.length ? "No suburb matches that search." : "No suburbs have results yet."}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="note">Each hexagon is about 400 m across and shows one sample building near its centre. Select a suburb to zoom to it.</p>
    </section>
  );
}
