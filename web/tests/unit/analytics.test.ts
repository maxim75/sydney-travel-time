import { describe, expect, it } from "vitest";
import { hexagonClickParams } from "../../lib/analytics";
import { fixtureSite, ONWARD_ID } from "../fixtures";

describe("analytics", () => {
  it("describes a clicked hexagon by its centre in degrees, suburb and dataset", () => {
    expect(hexagonClickParams(fixtureSite(), 0, ONWARD_ID)).toEqual({
      latitude: -33.87174, longitude: 151.20669, suburb: "Sydney", dataset: ONWARD_ID,
    });
  });
});
