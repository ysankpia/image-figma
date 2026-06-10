import type { ExportManifest, ProjectDetail } from "./types";

export function buildExportManifest(detail: ProjectDetail, exportedAt = new Date().toISOString()): ExportManifest {
  return {
    schema: "manual_ui_slices.v1",
    exportedAt,
    project: detail.project,
    pages: detail.pages.map((page, pageIndex) => ({
      pageId: page.id,
      originalName: page.originalName,
      original: `originals/page_${String(pageIndex + 1).padStart(4, "0")}.png`,
      width: page.width,
      height: page.height,
      slices: page.slices.map((slice, sliceIndex) => ({
        id: slice.id,
        name: slice.name,
        kind: slice.kind,
        filename: `slices/${page.id}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
        placement: { ...slice.bbox },
        selected: true
      }))
    }))
  };
}
