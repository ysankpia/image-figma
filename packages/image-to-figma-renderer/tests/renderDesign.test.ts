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
});
