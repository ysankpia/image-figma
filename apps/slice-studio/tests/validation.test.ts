import { describe, expect, it } from "vitest";
import { normalizeCutMode, normalizeSliceKind } from "../shared/validation";

describe("slice validation", () => {
  it("only accepts image assets", () => {
    expect(normalizeSliceKind("image")).toBe("image");
    expect(() => normalizeSliceKind("icon")).toThrow("slice kind must be image");
  });

  it("defaults unknown cut modes to rect", () => {
    expect(normalizeCutMode("shape")).toBe("shape");
    expect(normalizeCutMode("rect")).toBe("rect");
    expect(normalizeCutMode("old")).toBe("rect");
    expect(normalizeCutMode(undefined)).toBe("rect");
  });
});
