import { describe, expect, it } from "vitest";
import { classify, hasMorning, metricOf } from "../../lib/metrics";
import { fixtureDataset } from "../fixtures";

const onward = fixtureDataset("onward"), night = fixtureDataset("return");

describe("metrics", () => {
  it("bands journey times by their upper bounds", () => {
    const M = metricOf("time", onward);
    expect([M.band(30), M.band(31), M.band(150), M.band(151)]).toEqual([0, 1, 8, 9]);
    expect([M.labels[0], M.labels[1], M.labels[9]]).toEqual(["30 min or less", "31–45 min", "Over 150 min"]);
  });
  it("uses the time-to-get-there scale for return datasets", () => {
    expect(metricOf("time", night).title).toBe("Time to get there");
    expect(metricOf("walk", night).title).toBe("Walking time");
  });
  it("spreads rides over the ramp and caps them at five", () => {
    const M = metricOf("rides", onward);
    expect([M.band(0), M.band(1), M.band(7)]).toEqual([0, 2, 9]);
  });
  it("classifies every hexagon by status and journey time", () => {
    expect([...classify(onward, "time", "all", 7)]).toEqual([3, 5, 11, 1, 14, 2, 0]);
  });
  it("greys out trips the filter leaves out, and every non-trip", () => {
    expect([...classify(onward, "time", "train", 7)]).toEqual([3, 0, 0, 0, 0, 0, 0]);
    expect([...classify(onward, "time", "bus", 7)]).toEqual([0, 5, 0, 0, 0, 0, 0]);
  });
  it("shows next-morning trips apart in return datasets", () => {
    expect([...classify(night, "time", "all", 7)]).toEqual([4, 13, 9, 1, 14, 2, 0]);
    expect([...classify(night, "time", "tonight", 7)]).toEqual([4, 0, 9, 0, 0, 0, 0]);
  });
  it("knows which datasets have next-morning trips", () => {
    expect(hasMorning(night)).toBe(true);
    expect(hasMorning(onward)).toBe(false);
  });
});
