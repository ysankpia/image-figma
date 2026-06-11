import { normalizeDefaultSliceNames } from "./slice-names";
import type { ExportManifest, ProjectDetail } from "./types";

export function buildExportManifest(detail: ProjectDetail, exportedAt = new Date().toISOString()): ExportManifest {
  return {
    schema: "manual_ui_slices.v1",
    exportedAt,
    project: detail.project,
    pages: detail.pages.map((page, pageIndex) => {
      const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
      return {
        pageId: page.id,
        originalName: page.originalName,
        displayName: page.displayName,
        pageDirectory,
        original: `originals/${pageDirectory}.png`,
        width: page.width,
        height: page.height,
        slices: normalizeDefaultSliceNames(page.slices).map((slice, sliceIndex) => ({
          id: slice.id,
          name: slice.name,
          kind: slice.kind,
          cutMode: slice.cutMode,
          filename: `slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
          placement: { ...slice.bbox },
          selected: true
        }))
      };
    })
  };
}

export function pageExportDirectory(pageIndex: number, displayName: string): string {
  const base = `P${pageIndex}`;
  const suffix = slugPart(displayName);
  return suffix ? `${base}-${suffix}` : base;
}

function slugPart(value: string): string {
  return value
    .trim()
    .normalize("NFKD")
    .replace(/[^\p{Letter}\p{Number}_-]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}
