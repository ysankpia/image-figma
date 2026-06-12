import { describe, expect, it } from "vitest";
import { normalizeDSL, type DesignDSL } from "../src";
import { loadExample } from "./helpers";

describe("normalizeDSL", () => {
  it("fills renderer-friendly defaults", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    const sparse: DesignDSL = {
      ...dsl,
      root: {
        id: "root",
        type: "frame",
        layout: {
          x: 0.24,
          y: 0.26,
          width: 390.24,
          height: 844.26
        }
      }
    };

    const normalized = normalizeDSL(sparse);

    expect(normalized.root.role).toBe("unknown");
    expect(normalized.root.name).toBe("Frame / root");
    expect(normalized.root.children).toEqual([]);
    expect(normalized.root.meta).toEqual({});
    expect(normalized.root.style).toEqual({ opacity: 1, visible: true });
    expect(normalized.root.layout).toEqual({ x: 0, y: 0.5, width: 390, height: 844.5 });
  });

  it("normalizes children recursively", () => {
    const dsl = loadExample("mobile-list.dsl.json");
    const normalized = normalizeDSL(dsl);
    const card = normalized.root.children!.find((child) => child.id === "item_card_1")!;
    const cardChild = card.children!.find((child) => child.id === "item_title_1")!;

    expect(card.name).toBe("Group / item_card_1");
    expect(cardChild.name).toBe("Text / item_title_1");
    expect(cardChild.style?.visible).toBe(true);
    expect(cardChild.style?.opacity).toBe(1);
  });
});
