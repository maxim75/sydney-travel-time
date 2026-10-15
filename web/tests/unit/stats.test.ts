import { describe, expect, it } from "vitest";
import { classCounts, headerStats, median, sortRows, suburbRows, type SuburbRow } from "../../lib/stats";
import { fixtureDataset, fixtureSite } from "../fixtures";

describe("stats", () => {
  it("takes the median, rounding between the middle two", () => {
    expect([median([]), median([3]), median([1, 2]), median([1, 2, 3])]).toEqual([null, 3, 2, 2]);
  });
  it("summarises an onward dataset", () => {
    expect(headerStats(fixtureDataset("onward"), 7)).toEqual({
      computed: 6, pct: 6 / 7, median: 50, fastest: 25, morning: 0, tooFar: 1, noJourney: 1,
    });
  });
  it("leaves next-morning trips out of the return summary", () => {
    expect(headerStats(fixtureDataset("return"), 7)).toMatchObject({ median: 85, fastest: 40, morning: 1 });
  });
  it("lists suburbs with at least one trip", () => {
    expect(suburbRows(fixtureSite(), fixtureDataset("onward"))).toEqual([{
      name: "Sydney", total: 4, cells: [0, 1, 2, 6], done: 3, median: 50, fastest: 25, trainShare: 1 / 3,
    }]);
  });
  it("filters suburbs by a case-insensitive search", () => {
    const rows = suburbRows(fixtureSite(), fixtureDataset("onward"));
    expect(sortRows(rows, "SYD", "median", 1)).toHaveLength(1);
    expect(sortRows(rows, "hay", "median", 1)).toHaveLength(0);
  });
  it("sorts by the key in either direction, then by name", () => {
    const row = (name: string, median: number) => ({ name, median, fastest: 0, trainShare: 0, done: 0, total: 0, cells: [] }) as SuburbRow;
    const rows = [row("B", 10), row("C", 5), row("A", 10)];
    expect(sortRows(rows, "", "median", 1).map((r) => r.name)).toEqual(["C", "A", "B"]);
    expect(sortRows(rows, "", "median", -1).map((r) => r.name)).toEqual(["A", "B", "C"]);
  });
  it("counts hexagons per class", () => {
    const counts = classCounts(new Uint8Array([3, 3, 0, 14]));
    expect(counts).toHaveLength(15);
    expect([counts[0], counts[3], counts[14]]).toEqual([1, 2, 1]);
  });
});
