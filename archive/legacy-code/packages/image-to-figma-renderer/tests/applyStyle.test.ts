import { describe, expect, it } from "vitest";
import { applyBaseStyle, parseHexColor } from "../src/applyStyle";
import { FakeFigmaAdapter } from "./fakeAdapter";

describe("applyStyle", () => {
  it("applies basic fill, stroke, radius, opacity and visibility", () => {
    const adapter = new FakeFigmaAdapter();
    const node = adapter.createRectangle();

    applyBaseStyle(adapter, node, {
      fill: "#ffffff",
      stroke: { color: "#111111", width: 2 },
      radius: 8,
      opacity: 0.75,
      visible: false
    });

    const fake = adapter.nodes[0]!;
    expect(fake.fills?.[0]).toEqual({ type: "SOLID", color: { r: 1, g: 1, b: 1 }, opacity: 1 });
    expect(fake.strokes?.[0]?.color).toEqual({ r: 17 / 255, g: 17 / 255, b: 17 / 255 });
    expect(fake.strokeWeight).toBe(2);
    expect(fake.cornerRadius).toBe(8);
    expect(fake.opacity).toBe(0.75);
    expect(fake.visible).toBe(false);
  });

  it("falls back to black for invalid hex", () => {
    expect(parseHexColor("not-a-color")).toEqual({ r: 0, g: 0, b: 0 });
  });

  it("clears fills when fill is explicitly null", () => {
    const adapter = new FakeFigmaAdapter();
    const node = adapter.createFrame();

    applyBaseStyle(adapter, node, { fill: null });

    expect(adapter.nodes[0]!.fills).toEqual([]);
  });
});
