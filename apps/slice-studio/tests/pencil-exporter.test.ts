import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { buildPencilManifest, createRemainderPng } from "../server/pencil-package";
import type { ProjectDetail } from "../shared/types";

describe("pencil exporter", () => {
  it("clears selected slice rectangles from the remainder layer", async () => {
    const source = await sharp({
      create: {
        width: 8,
        height: 8,
        channels: 4,
        background: { r: 255, g: 0, b: 0, alpha: 1 }
      }
    }).png().toBuffer();

    const png = await createRemainderPng(source, [{ bbox: { x: 2, y: 2, width: 3, height: 3 } }]);
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

    expect(raw.info.width).toBe(8);
    expect(raw.info.height).toBe(8);
    expect(raw.data[(2 * raw.info.width + 2) * 4 + 3]).toBe(0);
    expect(raw.data[(6 * raw.info.width + 6) * 4 + 3]).toBe(255);
  });

  it("builds project.zip manifest paths for Pencil visible assets", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 1,
        sliceCount: 1
      },
      pages: [{
        id: "page_0001",
        projectId: "project_1",
        pageIndex: 1,
        originalName: "home.png",
        displayName: "首页",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "hero",
          kind: "image",
          cutMode: "card",
          bbox: { x: 1, y: 2, width: 30, height: 20 },
          selected: true
        }]
      }]
    };

    const manifest = buildPencilManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.schema).toBe("slice_studio_pencil_project_manifest.v1");
    expect(manifest.pencil.designPen).toBe("design.pen");
    expect(manifest.pages[0].original).toBe("assets/originals/P1-首页.png");
    expect(manifest.pages[0].remainder).toBe("assets/visible/remainders/P1-首页/remainder.png");
    expect(manifest.pages[0].slices[0].filename).toBe("assets/visible/slices/P1-首页/slice_0001.png");
    expect(manifest.pages[0].slices[0].cutMode).toBe("card");
  });
});
