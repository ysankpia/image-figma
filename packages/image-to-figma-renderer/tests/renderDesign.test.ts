import { describe, expect, it } from "vitest";
import { renderDesign } from "../src";
import mobileHome from "../../dsl-schema/examples/mobile-home.dsl.json";
import type { DesignDSL } from "@image-figma/dsl-schema";
import { FakeFigmaAdapter } from "./fakeAdapter";

describe("renderDesign", () => {
  it("renders mobile-home with fake adapter and continues past unsupported icon", async () => {
    const adapter = new FakeFigmaAdapter();
    const result = await renderDesign(mobileHome as DesignDSL, { figma: adapter });

    expect(result.success).toBe(true);
    expect(result.rootNodeId).toBe("fake_1");
    expect(result.renderedElementCount).toBe(6);
    expect(result.warnings).toContainEqual(
      expect.objectContaining({ code: "UNSUPPORTED_ELEMENT_TYPE", elementId: "search_icon" })
    );
    expect(adapter.findNodeByName("mobile_home")).toBeDefined();
    expect(adapter.findNodeByName("Original PNG Reference")?.visible).toBe(false);
    expect(adapter.findNodeByName("Text / title")?.characters).toBe("首页");
    expect(adapter.findNodeByName("Text / title")?.fontName).toEqual({ family: "Inter", style: "Semibold" });
    expect(adapter.findNodeByName("Text / title")?.textAutoResize).toBe("WIDTH_AND_HEIGHT");
    expect(adapter.findNodeByName("Shape / search_card")).toBeDefined();
    expect(adapter.findNodeByName("Image / banner")?.fills?.[0]?.type).toBe("IMAGE");
    expect(adapter.findNodeByName("Line / divider")).toBeDefined();
  });

  it("returns success false for invalid DSL", async () => {
    const adapter = new FakeFigmaAdapter();
    const invalid = { ...(mobileHome as DesignDSL), version: "0.2" };

    const result = await renderDesign(invalid as never, { figma: adapter });

    expect(result.success).toBe(false);
    expect(result.errors.some((error) => error.code === "UNSUPPORTED_DSL_VERSION")).toBe(true);
    expect(result.renderedElementCount).toBe(0);
  });

  it("warns on missing image asset but keeps rendering siblings", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);
    const banner = dsl.root.children!.find((child) => child.id === "banner")!;
    banner.source = { assetId: "missing_asset" };

    const result = await renderDesign(dsl, { figma: adapter, validate: false });

    expect(result.success).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "IMAGE_SOURCE_NOT_FOUND")).toBe(true);
    expect(adapter.findNodeByName("Line / divider")).toBeDefined();
  });

  it("warns on font load failure and keeps text editable", async () => {
    const adapter = new FakeFigmaAdapter({ failFontLoad: true });

    const result = await renderDesign(mobileHome as DesignDSL, { figma: adapter });

    expect(result.success).toBe(true);
    expect(result.warnings.some((warning) => warning.code === "FONT_LOAD_FAILED")).toBe(true);
    expect(adapter.findNodeByName("Text / title")?.characters).toBe("首页");
  });

  it("uses explicit DSL element names for Figma layer names", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);
    const title = dsl.root.children!.find((child) => child.id === "title")!;
    title.name = "Page Header / Text / 首页";

    const result = await renderDesign(dsl, { figma: adapter });

    expect(result.success).toBe(true);
    expect(adapter.findNodeByName("Page Header / Text / 首页")?.characters).toBe("首页");
  });

  it("renders M24 visible icon fallback cover and image nodes", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);
    dsl.assets.push({
      assetId: "asset_icon_candidate_001",
      type: "image",
      role: "asset_icon_visible_fallback",
      url: "http://localhost:8000/files/assets/task/icons/icon_candidate_001.png",
      format: "png",
      width: 20,
      height: 20,
      storage: "local"
    });
    dsl.root.children!.push(
      {
        id: "icon_fallback_cover_001",
        type: "shape",
        role: "icon_fallback_cover",
        name: "Icon Fallback Cover / 001",
        layout: { x: 10, y: 10, width: 24, height: 24 },
        style: { visible: true, opacity: 1, fill: "#FFFFFF", radius: 0 }
      },
      {
        id: "visible_icon_fallback_001",
        type: "image",
        role: "visible_icon_fallback",
        name: "Visible Icon Fallback / 001",
        layout: { x: 12, y: 12, width: 20, height: 20 },
        source: { assetId: "asset_icon_candidate_001" },
        imageFill: { mode: "fit" },
        style: { visible: true, opacity: 1 }
      }
    );

    const result = await renderDesign(dsl, { figma: adapter });

    expect(result.success).toBe(true);
    expect(adapter.findNodeByName("Icon Fallback Cover / 001")?.fills?.[0]).toEqual(
      expect.objectContaining({ type: "SOLID" })
    );
    expect(adapter.findNodeByName("Visible Icon Fallback / 001")?.fills?.[0]).toEqual(
      expect.objectContaining({ type: "IMAGE", scaleMode: "FIT" })
    );
  });

  it("ignores maskBBoxes and renders fallback region flat", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);

    const fallbackNode = {
      id: "fallback_region_1",
      type: "image" as const,
      role: "fallback_region",
      name: "Fallback Region / Page 1",
      layout: { x: 0, y: 0, width: 375, height: 812 },
      source: { assetId: "asset_banner" },
      style: { visible: true, opacity: 1 },
      meta: {
        maskBBoxes: [
          [10, 10, 40, 12],
          [15, 15, 10, 10]
        ]
      }
    };
    dsl.root.children!.push(fallbackNode);

    const result = await renderDesign(dsl, { figma: adapter, validate: false });

    expect(result.success).toBe(true);

    const rectangleNode = adapter.nodes.find(n => n.name === "Fallback Region / Page 1") as any;
    expect(rectangleNode).toBeDefined();
    expect(rectangleNode?.type).toBe("RECTANGLE");
    expect(rectangleNode?.fills).toBeDefined();
    expect(rectangleNode?.fills?.[0]?.type).toBe("IMAGE");
    expect(rectangleNode?.fills?.[0]?.imageHash).toBe("hash:http://localhost:8000/files/assets/task_mobile_home/banner.png");
    expect(rectangleNode?.visible).toBe(true);
    expect(rectangleNode?.opacity).toBe(1);

    // Ensure no boolean subtraction group is created.
    const subtractNode = adapter.nodes.find(n => n.type === "BOOLEAN_OPERATION");
    expect(subtractNode).toBeUndefined();
  });

  it("applies WIDTH_AND_HEIGHT to single-line text and HEIGHT to multi-line/paragraph text", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);

    // Add a multiline text block
    dsl.root.children!.push({
      id: "paragraph_text",
      type: "text",
      role: "body",
      name: "Text / paragraph",
      layout: { x: 16, y: 400, width: 358, height: 60 },
      style: { fontSize: 14, fontWeight: 400 },
      content: { text: "This is a long multiline description or paragraph that should wrap appropriately." }
    });

    // Add a text block that physically has a newline character
    dsl.root.children!.push({
      id: "newline_text",
      type: "text",
      role: "body",
      name: "Text / newline",
      layout: { x: 16, y: 500, width: 358, height: 20 },
      style: { fontSize: 14, fontWeight: 400 },
      content: { text: "Line 1\nLine 2" }
    });

    const result = await renderDesign(dsl, { figma: adapter, validate: false });
    expect(result.success).toBe(true);

    const singleLineNode = adapter.findNodeByName("Text / title");
    expect(singleLineNode?.textAutoResize).toBe("WIDTH_AND_HEIGHT");

    const paragraphNode = adapter.findNodeByName("Text / paragraph");
    expect(paragraphNode?.textAutoResize).toBe("HEIGHT");

    const newlineNode = adapter.findNodeByName("Text / newline");
    expect(newlineNode?.textAutoResize).toBe("HEIGHT");
  });

  it("renders transparent hierarchy groups with parent-local children", async () => {
    const adapter = new FakeFigmaAdapter();
    const dsl = structuredClone(mobileHome as DesignDSL);
    dsl.root.children!.push({
      id: "m38_container_unit_1",
      type: "group",
      role: "m38_container",
      name: "M38 Container / unit_1",
      layout: { x: 100, y: 200, width: 160, height: 60 },
      style: { fill: null, clipContent: false },
      children: [
        {
          id: "m38_child_text",
          type: "text",
          role: "m30_text_member",
          name: "Text / nested",
          layout: { x: 10, y: 12, width: 80, height: 20 },
          content: { text: "Nested" },
          style: { fontSize: 14, color: "#111111" }
        }
      ]
    });

    const result = await renderDesign(dsl, { figma: adapter, validate: false });

    expect(result.success).toBe(true);
    const group = adapter.findNodeByName("M38 Container / unit_1");
    expect(group?.fills).toEqual([]);
    expect(group?.layout).toEqual({ x: 100, y: 200, width: 160, height: 60 });
    expect(group?.children.map(child => child.name)).toEqual(["Text / nested"]);
    expect(group?.children[0]?.layout).toEqual({ x: 10, y: 12, width: 80, height: 20 });
  });
});
