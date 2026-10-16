import { describe, expect, it } from "vitest";
import { rememberDataset, rememberedDataset } from "../../lib/storage";

const memory = () => {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) } as unknown as Storage;
};
const broken = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
} as unknown as Storage;

describe("storage", () => {
  it("round-trips the chosen dataset", () => {
    const s = memory();
    rememberDataset("abc", s);
    expect(rememberedDataset(s)).toBe("abc");
  });
  it("returns null when storage throws", () => expect(rememberedDataset(broken)).toBeNull());
  it("ignores storage that throws on write", () => expect(() => rememberDataset("abc", broken)).not.toThrow());
  it("returns null without storage", () => expect(rememberedDataset(null)).toBeNull());
});
