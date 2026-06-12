import { describe, expect, it } from "vitest";
import { draftToBox, moveBox, normalizeBox, resizeBox } from "../shared/bbox";

describe("bbox helpers", () => {
  it("normalizes boxes into image bounds", () => {
    expect(normalizeBox({ x: -5, y: 4.4, width: 500, height: 8.5 }, { width: 100, height: 80 })).toEqual({
      x: 0,
      y: 4,
      width: 100,
      height: 9
    });
  });

  it("moves boxes without leaving bounds", () => {
    expect(moveBox({ x: 10, y: 10, width: 20, height: 20 }, 100, -30, { width: 90, height: 70 })).toEqual({
      x: 70,
      y: 0,
      width: 20,
      height: 20
    });
  });

  it("resizes boxes with a minimum size", () => {
    expect(resizeBox({ x: 10, y: 10, width: 40, height: 40 }, "nw", 20, 20, { width: 100, height: 100 })).toEqual({
      x: 30,
      y: 30,
      width: 20,
      height: 20
    });
  });

  it("creates draft boxes from diagonal drags", () => {
    expect(draftToBox({ x: 50, y: 60 }, { x: 10, y: 20 }, { width: 100, height: 100 })).toEqual({
      x: 10,
      y: 20,
      width: 40,
      height: 40
    });
  });
});
