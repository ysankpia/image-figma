import { describe, expect, it } from "vitest";
import { normalizeSliceKind } from "../shared/validation";

describe("slice validation", () => {
  it("only accepts image assets", () => {
    expect(normalizeSliceKind("image")).toBe("image");
    expect(() => normalizeSliceKind("icon")).toThrow("slice kind must be image");
  });
});
