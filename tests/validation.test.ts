import { describe, expect, it } from "vitest";
import { normalizeDefaultSliceNames } from "../shared/slice-names";
import { normalizeCutMode, normalizeSliceKind } from "../shared/validation";

describe("slice validation", () => {
  it("only accepts image assets", () => {
    expect(normalizeSliceKind("image")).toBe("image");
    expect(() => normalizeSliceKind("icon")).toThrow("slice kind must be image");
  });

  it("defaults unknown cut modes to rect", () => {
    expect(normalizeCutMode("shape")).toBe("subject");
    expect(normalizeCutMode("subject")).toBe("subject");
    expect(normalizeCutMode("card")).toBe("card");
    expect(normalizeCutMode("rect")).toBe("rect");
    expect(normalizeCutMode("old")).toBe("rect");
    expect(normalizeCutMode(undefined)).toBe("rect");
  });

  it("reindexes only default slice names and preserves user names", () => {
    const normalized = normalizeDefaultSliceNames([
      { sliceIndex: 4, name: "slice_04" },
      { sliceIndex: 9, name: "custom_logo" },
      { sliceIndex: 25, name: "slice_25" },
      { sliceIndex: 1, name: "Slice_0001" }
    ]);

    expect(normalized.map((slice) => slice.sliceIndex)).toEqual([1, 2, 3, 4]);
    expect(normalized.map((slice) => slice.name)).toEqual(["slice_01", "custom_logo", "slice_03", "slice_04"]);
  });
});
