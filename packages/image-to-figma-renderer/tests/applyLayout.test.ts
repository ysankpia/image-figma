import { describe, expect, it } from "vitest";
import { applyLayout } from "../src/applyLayout";
import { FakeFigmaAdapter } from "./fakeAdapter";

describe("applyLayout", () => {
  it("sets absolute position and size", () => {
    const adapter = new FakeFigmaAdapter();
    const node = adapter.createFrame();

    applyLayout(adapter, node, { x: 16, y: 24, width: 390, height: 844 });

    expect(adapter.nodes[0]!.layout).toEqual({ x: 16, y: 24, width: 390, height: 844 });
  });
});
