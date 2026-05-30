import { describe, expect, it } from "vitest";
import { type CodiaRuntimeDSL } from "@image-figma/dsl-schema";
import { renderCodiaRuntimeDesign } from "../src";
import { FakeFigmaAdapter } from "./fakeAdapter";

describe("renderCodiaRuntimeDesign", () => {
  it("renders Codia Runtime DSL 0.2 nodes with the fake adapter", async () => {
    const adapter = new FakeFigmaAdapter();

    const result = await renderCodiaRuntimeDesign(makeCodiaRuntimeDsl(), { figma: adapter });

    expect(result.success).toBe(true);
    expect(result.rootNodeId).toBe("fake_1");
    expect(result.renderedElementCount).toBe(7);
    expect(result.warnings).toEqual([]);
    expect(adapter.findNodeByName("Root")).toBeDefined();
    expect(adapter.findNodeByName("Groups")?.children.map((child) => child.name)).toEqual([
      "Image",
      "Button",
      "首页"
    ]);
    expect(adapter.findNodeByName("Button")?.children.map((child) => child.name)).toEqual(["Background", "Pay"]);
    expect(adapter.findNodeByName("首页")?.characters).toBe("首页");
    expect(adapter.findNodeByName("首页")?.textAutoResize).toBe("WIDTH_AND_HEIGHT");
    expect(adapter.findNodeByName("Image")?.fills?.[0]).toEqual(
      expect.objectContaining({ type: "IMAGE", scaleMode: "FIT" })
    );
    expect(adapter.findNodeByName("Background")?.fills?.[0]).toEqual(expect.objectContaining({ type: "SOLID" }));
  });

  it("returns validation errors for invalid Codia Runtime DSL", async () => {
    const adapter = new FakeFigmaAdapter();
    const invalid = { ...makeCodiaRuntimeDsl(), version: "0.1" };

    const result = await renderCodiaRuntimeDesign(invalid as never, { figma: adapter });

    expect(result.success).toBe(false);
    expect(result.renderedElementCount).toBe(0);
    expect(result.errors.some((error) => error.code === "UNSUPPORTED_CODIA_RUNTIME_DSL_VERSION")).toBe(true);
  });

  it("warns and renders a placeholder for image nodes without assets", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = makeCodiaRuntimeDsl();
    const image = dsl.root.children![0]!.children!.find((child) => child.id === "cover")!;
    delete image.image;

    const result = await renderCodiaRuntimeDesign(dsl, { figma: adapter });

    expect(result.success).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "CODIA_RUNTIME_IMAGE_SOURCE_NOT_FOUND")).toBe(true);
    expect(adapter.findNodeByName("Image")?.fills?.[0]).toEqual(expect.objectContaining({ type: "SOLID" }));
  });

  it("continues after font and image loading failures", async () => {
    const adapter = new FakeFigmaAdapter({
      failFontLoad: true,
      failImageUrls: new Set(["http://localhost:8000/files/assets/task/cover.png"])
    });

    const result = await renderCodiaRuntimeDesign(makeCodiaRuntimeDsl(), { figma: adapter });

    expect(result.success).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "FONT_LOAD_FAILED")).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "IMAGE_LOAD_FAILED")).toBe(true);
    expect(adapter.findNodeByName("首页")?.characters).toBe("首页");
    expect(adapter.findNodeByName("Image")?.fills?.[0]).toEqual(expect.objectContaining({ type: "SOLID" }));
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
          id: "group_1",
          role: "ViewGroup",
          type: "frame",
          name: "Groups",
          bbox: { x: 0, y: 0, width: 390, height: 844 },
          style: { fill: null },
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
              image: { assetId: "asset_cover", mode: "fit" }
            },
            {
              id: "button",
              role: "Button",
              type: "frame",
              name: "Button",
              bbox: { x: 16, y: 160, width: 120, height: 44 },
              children: [
                {
                  id: "button_label",
                  role: "TextView",
                  type: "text",
                  name: "Pay",
                  bbox: { x: 28, y: 172, width: 72, height: 20 },
                  text: { characters: "Pay" },
                  style: { fontSize: 14, color: "#FFFFFF", fontWeight: 600 }
                },
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
        }
      ]
    }
  };
}
