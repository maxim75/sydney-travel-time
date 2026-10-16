import { describe, expect, it } from "vitest";
import { fmt, km, mins } from "../../lib/format";

describe("format", () => {
  it("formats counts with Australian thousands separators", () => expect(fmt(18970)).toBe("18,970"));
  it("formats distances in metres below 1 km", () => expect(km(950)).toBe("950 m"));
  it("formats distances in km with one decimal from 1 km", () => expect(km(1234)).toBe("1.2 km"));
  it("formats durations under two hours in minutes", () => expect(mins(119)).toBe("119 min"));
  it("formats durations from two hours in hours and minutes", () => expect(mins(125)).toBe("2 h 5 min"));
});
