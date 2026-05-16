import { describe, expect, it } from "vitest";
import { type DSLElement, validateDSL } from "../src";
import { createSchemaValidator, loadExample } from "./helpers";

describe("validateDSL", () => {
  it("accepts valid example DSL files", () => {
    const validateSchema = createSchemaValidator();

    for (const file of [
      "mobile-home.dsl.json",
      "mobile-list.dsl.json",
      "mobile-detail.dsl.json",
      "simple-admin.dsl.json"
    ]) {
      const dsl = loadExample(file);
      expect(validateSchema(dsl), file).toBe(true);
      expect(validateDSL(dsl), file).toEqual({ valid: true, errors: [], warnings: [] });
    }
  });

  it("rejects a missing version", () => {
    const dsl = loadExample("mobile-home.dsl.json") as unknown as Record<string, unknown>;
    delete dsl.version;

    const result = validateDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "UNSUPPORTED_DSL_VERSION")).toBe(true);
  });

  it("rejects an invalid element type", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    dsl.root.children![0]!.type = "component" as never;

    const result = validateDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "ELEMENT_TYPE_INVALID")).toBe(true);
  });

  it("rejects an element without layout", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    delete (dsl.root.children![0]! as Partial<DSLElement>).layout;

    const result = validateDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "LAYOUT_REQUIRED")).toBe(true);
  });

  it("rejects text without content.text", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    const title = dsl.root.children!.find((child) => child.id === "title")!;
    delete title.content;

    const result = validateDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "TEXT_CONTENT_REQUIRED")).toBe(true);
  });

  it("rejects an image that references a missing assetId", () => {
    const dsl = loadExample("mobile-home.dsl.json");
    const banner = dsl.root.children!.find((child) => child.id === "banner")!;
    banner.source = { assetId: "missing_asset" };

    const result = validateDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "ASSET_NOT_FOUND")).toBe(true);
  });
});
