import { describe, expect, it } from "vitest";
import { type DraftRuntimeDSL, validateDraftRuntimeDSL } from "../src";

describe("validateDraftRuntimeDSL", () => {
  it("accepts a valid Draft Runtime DSL document", () => {
    const result = validateDraftRuntimeDSL(makeDraftRuntimeDsl());

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual([]);
  });

  it("rejects the wrong runtime identity", () => {
    const dsl = { ...makeDraftRuntimeDsl(), kind: "codia_runtime", version: "0.2" };

    const result = validateDraftRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "UNSUPPORTED_DRAFT_RUNTIME_DSL_VERSION")).toBe(true);
    expect(result.errors.some((error) => error.code === "DRAFT_RUNTIME_KIND_INVALID")).toBe(true);
  });

  it("rejects text nodes without characters", () => {
    const dsl = makeDraftRuntimeDsl();
    delete dsl.root.children![0]!.text;

    const result = validateDraftRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "TEXT_CONTENT_REQUIRED")).toBe(true);
  });

  it("rejects missing declared image assets", () => {
    const dsl = makeDraftRuntimeDsl();
    dsl.root.children![1]!.image = { assetId: "missing", mode: "fill" };

    const result = validateDraftRuntimeDSL(dsl);

    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.code === "ASSET_NOT_FOUND")).toBe(true);
  });
});

function makeDraftRuntimeDsl(): DraftRuntimeDSL {
  return {
    version: "1.0",
    kind: "draft_runtime",
    taskId: "task_draft_runtime",
    page: { name: "Draft", width: 390, height: 844 },
    assets: [
      {
        assetId: "asset_cover",
        type: "image",
        url: "assets/asset_cover.png",
        format: "png",
        width: 120,
        height: 80
      }
    ],
    root: {
      id: "root",
      type: "frame",
      name: "Draft",
      bbox: { x: 0, y: 0, width: 390, height: 844 },
      children: [
        {
          id: "title",
          type: "text",
          name: "Title",
          bbox: { x: 16, y: 24, width: 80, height: 24 },
          text: { characters: "首页" },
          style: { fontSize: 16, color: "#111111", fontWeight: 600 }
        },
        {
          id: "cover",
          type: "image",
          name: "Cover",
          bbox: { x: 16, y: 64, width: 120, height: 80 },
          image: { assetId: "asset_cover", mode: "fill" }
        }
      ]
    }
  };
}
