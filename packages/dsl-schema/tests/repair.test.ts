import { describe, expect, it } from "vitest";
import { repairDSL } from "../src";
import { loadExample } from "./helpers";

describe("repairDSL", () => {
  it("repairs light style issues without hiding severe validation errors", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    const searchCard = dsl.root.children!.find((child) => child.id === "search_card")!;
    searchCard.style = {
      opacity: 2,
      radius: -4
    };

    const result = repairDSL(dsl);
    const repairedSearchCard = result.dsl.root.children!.find((child) => child.id === "search_card")!;

    expect(repairedSearchCard.style?.opacity).toBe(1);
    expect(repairedSearchCard.style?.radius).toBe(0);
    expect(result.repairs.map((repair) => repair.code)).toContain("OPACITY_CLAMPED");
    expect(result.repairs.map((repair) => repair.code)).toContain("RADIUS_REPAIRED");
    expect(result.validation.valid).toBe(true);
  });

  it("does not swallow missing text content", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    const title = dsl.root.children!.find((child) => child.id === "title")!;
    delete title.content;

    const result = repairDSL(dsl);

    expect(result.validation.valid).toBe(false);
    expect(result.validation.errors.some((error) => error.code === "TEXT_CONTENT_REQUIRED")).toBe(true);
  });
});
