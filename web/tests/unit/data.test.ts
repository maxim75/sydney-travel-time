import { describe, expect, it } from "vitest";
import { emptyOverlay, fetchJson, loadDataset, pickInitialDataset } from "../../lib/data";
import { fixtureSite, ONWARD_ID, RETURN_ID } from "../fixtures";

const respond = (status: number, body: unknown = {}) => async () => new Response(JSON.stringify(body), { status });

describe("data", () => {
  it("parses a successful response", async () => {
    expect(await fetchJson("site.json", respond(200, { total: 7 }))).toEqual({ total: 7 });
  });
  it("throws with the HTTP status on failure", async () => {
    await expect(fetchJson("site.json", respond(404))).rejects.toThrow("HTTP 404");
  });
  it("requests map_data/<encoded id>.json", async () => {
    const urls: string[] = [];
    await loadDataset("a b", async (url) => { urls.push(url); return new Response("{}"); });
    expect(urls).toEqual(["/map_data/a%20b.json"]);
  });
  it("builds an empty overlay with every hexagon not computed", () => {
    const o = emptyOverlay(3);
    expect(o.status).toEqual([0, 0, 0]);
    expect(o.building).toBeNull();
    expect(o.computed).toBe(0);
  });
  it("restores a remembered dataset that still exists", () => {
    expect(pickInitialDataset(fixtureSite().datasets, RETURN_ID)).toBe(RETURN_ID);
  });
  it("falls back to the first dataset when the remembered one is gone", () => {
    expect(pickInitialDataset(fixtureSite().datasets, "GONE")).toBe(ONWARD_ID);
    expect(pickInitialDataset(fixtureSite().datasets, null)).toBe(ONWARD_ID);
  });
  it("picks nothing when there are no datasets", () => expect(pickInitialDataset([], "x")).toBeNull());
});
