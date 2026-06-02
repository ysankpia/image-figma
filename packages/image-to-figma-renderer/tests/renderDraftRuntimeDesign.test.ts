import { describe, expect, it } from "vitest";
import { type DraftRuntimeDSL } from "@image-figma/dsl-schema";
import { renderDraftRuntimeDesign } from "../src";
import { FakeFigmaAdapter } from "./fakeAdapter";

describe("renderDraftRuntimeDesign", () => {
  it("renders Draft Runtime DSL nodes with assets and text above raster order", async () => {
    const adapter = new FakeFigmaAdapter();

    const result = await renderDraftRuntimeDesign(makeDraftRuntimeDsl(), {
      figma: adapter,
      assetBaseUrl: "http://localhost:8000/api/draft-preview/task_draft_runtime"
    });

    expect(result.success).toBe(true);
    expect(result.renderedElementCount).toBe(4);
    expect(result.warnings).toEqual([]);
    expect(adapter.findNodeByName("Draft")).toBeDefined();
    expect(adapter.findNodeByName("Background")?.cornerRadius).toBe(8);
    expect(adapter.findNodeByName("Cover")?.fills?.[0]).toEqual(expect.objectContaining({ type: "IMAGE" }));
    expect(adapter.findNodeByName("Title")?.characters).toBe("首页");
    expect(adapter.findNodeByName("Title")?.textAutoResize).toBe("NONE");
    expect(adapter.imageSources[0]?.url).toBe(
      "http://localhost:8000/api/draft-preview/task_draft_runtime/assets/asset_cover.png"
    );
  });

  it("returns validation errors for invalid Draft Runtime DSL", async () => {
    const adapter = new FakeFigmaAdapter();
    const invalid = { ...makeDraftRuntimeDsl(), kind: "codia_runtime" };

    const result = await renderDraftRuntimeDesign(invalid as never, { figma: adapter });

    expect(result.success).toBe(false);
    expect(result.errors.some((error) => error.code === "DRAFT_RUNTIME_KIND_INVALID")).toBe(true);
  });

  it("continues after image loading failures", async () => {
    const adapter = new FakeFigmaAdapter({
      failImageUrls: new Set(["http://localhost:8000/api/draft-preview/task_draft_runtime/assets/asset_cover.png"])
    });

    const result = await renderDraftRuntimeDesign(makeDraftRuntimeDsl(), {
      figma: adapter,
      assetBaseUrl: "http://localhost:8000/api/draft-preview/task_draft_runtime"
    });

    expect(result.success).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "IMAGE_LOAD_FAILED")).toBe(true);
    expect(adapter.findNodeByName("Title")?.characters).toBe("首页");
  });

  it("maps Draft Runtime font families and weights to Figma font styles", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = makeDraftRuntimeDsl();
    dsl.root.children = [
      {
        id: "medium",
        type: "text",
        name: "Medium Text",
        bbox: { x: 10, y: 10, width: 100, height: 24 },
        text: { characters: "确认" },
        style: { fontFamily: "PingFang SC", fontSize: 16, fontWeight: 500, color: "#111111" }
      },
      {
        id: "semibold",
        type: "text",
        name: "Semibold Text",
        bbox: { x: 10, y: 40, width: 100, height: 24 },
        text: { characters: "标题" },
        style: { fontFamily: "PingFang SC", fontSize: 16, fontWeight: 600, color: "#111111" }
      },
      {
        id: "bold",
        type: "text",
        name: "Bold Text",
        bbox: { x: 10, y: 70, width: 100, height: 24 },
        text: { characters: "100" },
        style: { fontSize: 16, fontWeight: 700, color: "#111111" }
      }
    ];

    const result = await renderDraftRuntimeDesign(dsl, { figma: adapter });

    expect(result.success).toBe(true);
    expect(adapter.findNodeByName("Medium Text")?.fontName).toEqual({ family: "PingFang SC", style: "Medium" });
    expect(adapter.findNodeByName("Semibold Text")?.fontName).toEqual({ family: "PingFang SC", style: "Semibold" });
    expect(adapter.findNodeByName("Bold Text")?.fontName).toEqual({ family: "Inter", style: "Bold" });
    expect(adapter.findNodeByName("Medium Text")?.textAutoResize).toBe("NONE");
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
          id: "cover",
          type: "image",
          name: "Cover",
          bbox: { x: 16, y: 64, width: 120, height: 80 },
          z: 10,
          image: { assetId: "asset_cover", mode: "fill" }
        },
        {
          id: "title",
          type: "text",
          name: "Title",
          bbox: { x: 16, y: 24, width: 80, height: 24 },
          z: 20,
          text: { characters: "首页" },
          style: { fontSize: 16, color: "#111111", fontWeight: 600 }
        },
        {
          id: "background",
          type: "shape",
          name: "Background",
          bbox: { x: 8, y: 8, width: 180, height: 160 },
          z: 0,
          style: { fill: "#F5F5F5", cornerRadius: 8 }
        }
      ]
    }
  };
}
