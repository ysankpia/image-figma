import { describe, expect, it } from "vitest";
import { buildAssetMap, resolveImageSource } from "../src";
import mobileHome from "../../dsl-schema/examples/mobile-home.dsl.json";
import type { DesignDSL } from "@image-figma/dsl-schema";

describe("assetResolver", () => {
  it("resolves image element assetId to an asset URL", () => {
    const dsl = mobileHome as DesignDSL;
    const assetMap = buildAssetMap(dsl.assets);
    const banner = dsl.root.children!.find((child) => child.id === "banner")!;

    expect(resolveImageSource(banner, assetMap)).toEqual({
      assetId: "asset_banner",
      url: "http://localhost:8000/files/assets/task_mobile_home/banner.png"
    });
  });

  it("applies assetBaseUrl only to relative URLs", () => {
    const dsl = mobileHome as DesignDSL;
    const assetMap = buildAssetMap([
      {
        assetId: "relative",
        type: "image",
        url: "/files/example.png",
        format: "png"
      }
    ]);
    const element = {
      ...dsl.root.children!.find((child) => child.id === "banner")!,
      source: { assetId: "relative" }
    };

    expect(resolveImageSource(element, assetMap, "http://localhost:8000")).toEqual({
      assetId: "relative",
      url: "http://localhost:8000/files/example.png"
    });
  });
});
