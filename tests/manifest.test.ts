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
        displayName: "",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        thumbnailUrl: "/thumbnail",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "banner",
          kind: "image",
          cutMode: "rect",
          bbox: { x: 1, y: 2, width: 30, height: 20 },
          selected: true
        }]
      }]
    };
    const manifest = buildExportManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.pages[0].pageDirectory).toBe("P1");
    expect(manifest.pages[0].original).toBe("originals/P1.png");
    expect(manifest.pages[0].slices[0].filename).toBe("slices/P1/slice_0001.png");
    expect(manifest.pages[0].slices[0].cutMode).toBe("rect");
    expect(manifest.pages[0].slices[0].placement).toEqual({ x: 1, y: 2, width: 30, height: 20 });
  });

  it("includes editable page names in export paths", () => {
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
        thumbnailUrl: "/thumbnail",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "banner",
          kind: "image",
          cutMode: "subject",
          bbox: { x: 1, y: 2, width: 30, height: 20 },
          selected: true
        }]
      }]
    };
    const manifest = buildExportManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.pages[0].displayName).toBe("首页");
    expect(manifest.pages[0].pageDirectory).toBe("P1-首页");
    expect(manifest.pages[0].original).toBe("originals/P1-首页.png");
    expect(manifest.pages[0].slices[0].filename).toBe("slices/P1-首页/slice_0001.png");
    expect(manifest.pages[0].slices[0].cutMode).toBe("subject");
  });

  it("uses current page indexes instead of stable page ids for export order", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 2,
        sliceCount: 1
      },
      pages: [
        {
          id: "page_0002",
          projectId: "project_1",
          pageIndex: 1,
          originalName: "orders.png",
          displayName: "订单页",
          width: 100,
          height: 80,
          sourceUrl: "/source/orders",
          thumbnailUrl: "/thumbnail/orders",
          slices: [{
            id: "slice_1",
            projectId: "project_1",
            pageId: "page_0002",
            sliceIndex: 1,
            name: "asset",
            kind: "image",
            cutMode: "rect",
            bbox: { x: 1, y: 2, width: 10, height: 10 },
            selected: true
          }]
        },
        {
          id: "page_0001",
          projectId: "project_1",
          pageIndex: 2,
          originalName: "home.png",
          displayName: "首页",
          width: 100,
          height: 80,
          sourceUrl: "/source/home",
          thumbnailUrl: "/thumbnail/home",
          slices: []
        }
      ]
    };

    const manifest = buildExportManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.pages.map((page) => page.pageDirectory)).toEqual(["P1-订单页", "P2-首页"]);
    expect(manifest.pages[0].slices[0].filename).toBe("slices/P1-订单页/slice_0001.png");
  });

  it("normalizes default slice names in exported manifests", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 1,
        sliceCount: 3
      },
      pages: [{
        id: "page_0001",
        projectId: "project_1",
        pageIndex: 1,
        originalName: "home.png",
        displayName: "",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        thumbnailUrl: "/thumbnail",
        slices: [
          {
            id: "slice_a",
            projectId: "project_1",
            pageId: "page_0001",
            sliceIndex: 1,
            name: "slice_25",
            kind: "image",
            cutMode: "rect",
            bbox: { x: 1, y: 2, width: 10, height: 10 },
            selected: true
          },
          {
            id: "slice_b",
            projectId: "project_1",
            pageId: "page_0001",
            sliceIndex: 2,
            name: "custom_logo",
            kind: "image",
            cutMode: "rect",
            bbox: { x: 11, y: 2, width: 10, height: 10 },
            selected: true
          },
          {
            id: "slice_c",
            projectId: "project_1",
            pageId: "page_0001",
            sliceIndex: 3,
            name: "slice_25",
            kind: "image",
            cutMode: "rect",
            bbox: { x: 21, y: 2, width: 10, height: 10 },
            selected: true
          }
        ]
      }]
    };

    const manifest = buildExportManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.pages[0].slices.map((slice) => slice.name)).toEqual(["slice_01", "custom_logo", "slice_03"]);
  });
});
