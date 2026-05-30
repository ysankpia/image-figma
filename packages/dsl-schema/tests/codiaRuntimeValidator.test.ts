import { describe, expect, it } from "vitest";
import { type CodiaRuntimeDSL, validateCodiaRuntimeDSL, validateDSL } from "../src";

describe("validateCodiaRuntimeDSL", () => {
  it("accepts a valid Codia Runtime DSL 0.2 document", () => {
    const result = validateCodiaRuntimeDSL(makeCodiaRuntimeDsl());

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual([]);
  });

  it("keeps DesignDSL v0.1 validator isolated from DSL 0.2", () => {
    const result = validateDSL(makeCodiaRuntimeDsl() as never);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "UNSUPPORTED_DSL_VERSION")).toBe(true);
  });

  it("rejects a missing kind", () => {
    const dsl = makeCodiaRuntimeDsl() as unknown as Record<string, unknown>;
    delete dsl.kind;

    const result = validateCodiaRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "CODIA_RUNTIME_KIND_INVALID")).toBe(true);
  });

  it("rejects invalid roles and node types", () => {
    const dsl = makeCodiaRuntimeDsl();
    dsl.root.children![0]!.role = "m29_text" as never;
    dsl.root.children![0]!.type = "line" as never;

    const result = validateCodiaRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "CODIA_RUNTIME_ROLE_INVALID")).toBe(true);
    expect(result.errors.some((error) => error.code === "ELEMENT_TYPE_INVALID")).toBe(true);
  });

  it("rejects text nodes without characters", () => {
    const dsl = makeCodiaRuntimeDsl();
    const title = dsl.root.children!.find((child) => child.id === "title")!;
    delete title.text;

    const result = validateCodiaRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "TEXT_CONTENT_REQUIRED")).toBe(true);
  });

  it("warns for image placeholders and rejects missing declared asset ids", () => {
    const placeholderDsl = makeCodiaRuntimeDsl();
    const image = placeholderDsl.root.children!.find((child) => child.id === "cover")!;
    delete image.image;

    const placeholderResult = validateCodiaRuntimeDSL(placeholderDsl);

    expect(placeholderResult.valid).toBe(true);
    expect(placeholderResult.warnings.some((warning) => warning.code === "IMAGE_SOURCE_MISSING")).toBe(true);

    const invalidAssetDsl = makeCodiaRuntimeDsl();
    const invalidImage = invalidAssetDsl.root.children!.find((child) => child.id === "cover")!;
    invalidImage.image = { assetId: "missing_asset", mode: "fill" };

    const invalidAssetResult = validateCodiaRuntimeDSL(invalidAssetDsl);

    expect(invalidAssetResult.valid).toBe(false);
    expect(invalidAssetResult.errors.some((error) => error.code === "ASSET_NOT_FOUND")).toBe(true);
  });

  it("rejects duplicate ids", () => {
    const dsl = makeCodiaRuntimeDsl();
    dsl.root.children!.push({
      id: "title",
      role: "TextView",
      type: "text",
      bbox: { x: 12, y: 80, width: 80, height: 20 },
      text: { characters: "Duplicate" }
    });

    const result = validateCodiaRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "ELEMENT_ID_DUPLICATE")).toBe(true);
  });
});

function makeCodiaRuntimeDsl(): CodiaRuntimeDSL {
  return {
    version: "0.2",
    kind: "codia_runtime",
    taskId: "task_codia_runtime",
    page: {
      name: "Codia Beta",
      width: 390,
      height: 844,
      background: { type: "color", value: "#FFFFFF" }
    },
    assets: [
      {
        assetId: "asset_cover",
        type: "image",
        role: "ImageView",
        url: "http://localhost:8000/files/assets/task/cover.png",
        format: "png",
        width: 120,
        height: 80,
        storage: "local"
      }
    ],
    root: {
      id: "root",
      role: "Root",
      type: "frame",
      name: "Root",
      bbox: { x: 0, y: 0, width: 390, height: 844 },
      style: { fill: "#FFFFFF" },
      children: [
        {
          id: "title",
          role: "TextView",
          type: "text",
          name: "首页",
          bbox: { x: 16, y: 24, width: 80, height: 24 },
          text: { characters: "首页" },
          style: { fontSize: 16, color: "#111111", fontWeight: 600 }
        },
        {
          id: "cover",
          role: "ImageView",
          type: "image",
          name: "Image",
          bbox: { x: 16, y: 64, width: 120, height: 80 },
          image: { assetId: "asset_cover", mode: "fill" }
        },
        {
          id: "button",
          role: "Button",
          type: "frame",
          name: "Button",
          bbox: { x: 16, y: 160, width: 120, height: 44 },
          children: [
            {
              id: "button_bg",
              role: "bg_Button",
              type: "shape",
              name: "Background",
              bbox: { x: 0, y: 0, width: 120, height: 44 },
              style: { fill: "#2563EB", radius: 8 }
            }
          ]
        }
      ]
    },
    meta: {
      source: "go_codiacompile"
    }
  };
}
