import { describe, expect, it } from "vitest";
import { buildExportManifest } from "../shared/manifest";
import type { ProjectDetail } from "../shared/types";

describe("manifest", () => {
  it("builds stable export paths", () => {
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
        width: 100,
        height: 80,
        sourceUrl: "/source",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "banner",
          kind: "image",
          bbox: { x: 1, y: 2, width: 30, height: 20 },
          selected: true
        }]
      }]
    };
    const manifest = buildExportManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.pages[0].original).toBe("originals/page_0001.png");
    expect(manifest.pages[0].slices[0].filename).toBe("slices/page_0001/slice_0001.png");
    expect(manifest.pages[0].slices[0].placement).toEqual({ x: 1, y: 2, width: 30, height: 20 });
  });
});
