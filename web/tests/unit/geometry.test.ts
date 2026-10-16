import { describe, expect, it } from "vitest";
import { buildGeometry, COS } from "../../lib/geometry";
import { fixtureSite } from "../fixtures";

describe("geometry", () => {
  const g = buildGeometry(fixtureSite());
  it("keeps six vertices per hexagon", () => {
    expect(g.n).toBe(7);
    expect(g.start[7]).toBe(42);
  });
  it("measures the circumradius in world units (x scaled by cos latitude)", () => {
    expect(g.R).toBeCloseTo(200 * COS, 5);
  });
  it("finds the hexagon under a point", () => {
    expect(g.cellAt(g.cx[0], g.cy[0])).toBe(0);
    expect(g.cellAt(g.cx[3] + 1, g.cy[3] - 1)).toBe(3);
  });
  it("finds nothing far from every hexagon", () => expect(g.cellAt(g.cx[0] + 5000, g.cy[0])).toBe(-1));
  it("bounds every centre", () => {
    expect(g.minX).toBe(Math.min(...g.cx));
    expect(g.maxY).toBe(Math.max(...g.cy));
  });
});
